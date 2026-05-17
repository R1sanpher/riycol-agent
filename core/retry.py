"""
Retry and circuit breaker primitives for resilient LLM and API calls.

RetryPolicy — declarative retry configuration
retry()    — decorator: exponential backoff + jitter
CircuitBreaker — standard three-state model (closed/open/half-open)
CircuitOpenError — raised when circuit rejects a call
"""
import time, random, functools, threading
from dataclasses import dataclass, field
from typing import Callable, TypeVar, Any
from core.logger import log

T = TypeVar("T")

# ============================================================
# RetryPolicy & retry decorator
# ============================================================


@dataclass
class RetryPolicy:
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    backoff: float = 2.0
    retryable_exceptions: tuple[type[BaseException], ...] = (Exception,)
    jitter: bool = True


def retry(
    policy: RetryPolicy | None = None,
    *,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff: float = 2.0,
    retryable: tuple[type[BaseException], ...] | None = None,
    jitter: bool = True,
) -> Callable:
    """Decorator: retry on failure with exponential backoff and optional jitter.

    Usage:
        @retry(max_attempts=3, base_delay=1.0)
        def call_api(prompt): ...

        @retry(RetryPolicy(max_attempts=5, retryable=(ConnectionError, TimeoutError)))
        def fetch_url(url): ...
    """
    if policy is None:
        policy = RetryPolicy(
            max_attempts=max_attempts,
            base_delay=base_delay,
            max_delay=max_delay,
            backoff=backoff,
            retryable_exceptions=retryable or (Exception,),
            jitter=jitter,
        )

    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exc: Exception | None = None
            for attempt in range(policy.max_attempts):
                try:
                    return fn(*args, **kwargs)
                except policy.retryable_exceptions as e:
                    last_exc = e
                    if attempt + 1 >= policy.max_attempts:
                        log.error(f"Retry exhausted for {fn.__name__}: {e}")
                        raise
                    delay = min(
                        policy.base_delay * (policy.backoff ** attempt),
                        policy.max_delay,
                    )
                    if policy.jitter:
                        delay *= random.uniform(0.75, 1.25)
                    log.warn(
                        f"Retry {attempt + 1}/{policy.max_attempts} for {fn.__name__}: "
                        f"{e} — waiting {delay:.1f}s"
                    )
                    time.sleep(delay)
                except Exception:
                    raise
            raise last_exc  # type: ignore[misc]

        return wrapper

    return decorator


# ============================================================
# CircuitBreaker
# ============================================================


@dataclass
class _CircuitState:
    name: str
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    half_open_limit: int = 2

    _state: str = "closed"
    _failure_count: int = 0
    _last_failure_time: float = 0.0
    _half_open_successes: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)


class CircuitOpenError(Exception):
    """Raised when a call is rejected because the circuit is open."""
    pass


class CircuitBreaker:
    """Standard three-state circuit breaker for model backends.

    States:
      closed   — calls pass through; failures increment counter
      open     — calls rejected immediately; after recovery_timeout, transitions to half_open
      half_open — limited calls allowed; success closes circuit, failure re-opens
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_limit: int = 2,
    ):
        self._s = _CircuitState(
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            half_open_limit=half_open_limit,
        )

    @property
    def state(self) -> str:
        with self._s._lock:
            self._transition_if_needed()
            return self._s._state

    @property
    def is_open(self) -> bool:
        return self.state == "open"

    # ---- atomic state machine ----

    def _transition_if_needed(self):
        """Must be called with lock held."""
        if self._s._state == "open":
            if time.time() - self._s._last_failure_time >= self._s.recovery_timeout:
                self._s._state = "half_open"
                self._s._half_open_successes = 0
                log.info(f"CircuitBreaker[{self._s.name}]: open→half_open")

    def record_success(self):
        with self._s._lock:
            if self._s._state == "half_open":
                self._s._half_open_successes += 1
                if self._s._half_open_successes >= self._s.half_open_limit:
                    self._s._state = "closed"
                    self._s._failure_count = 0
                    log.info(f"CircuitBreaker[{self._s.name}]: half_open→closed")
            elif self._s._state == "closed":
                self._s._failure_count = 0

    def record_failure(self):
        with self._s._lock:
            self._s._failure_count += 1
            self._s._last_failure_time = time.time()
            if (
                self._s._state == "closed"
                and self._s._failure_count >= self._s.failure_threshold
            ):
                self._s._state = "open"
                log.warn(
                    f"CircuitBreaker[{self._s.name}]: closed→open "
                    f"({self._s._failure_count} failures)"
                )
            elif self._s._state == "half_open":
                self._s._state = "open"
                log.warn(f"CircuitBreaker[{self._s.name}]: half_open→open")

    # ---- public call protection ----

    def call(self, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Call fn with circuit protection.

        Raises:
            CircuitOpenError: if the circuit is open
            Original exception: if fn raises
        """
        with self._s._lock:
            self._transition_if_needed()
            if self._s._state == "open":
                raise CircuitOpenError(
                    f"CircuitBreaker[{self._s.name}] is open — "
                    f"retry after {self._s.recovery_timeout:.0f}s"
                )

        try:
            result = fn(*args, **kwargs)
        except Exception:
            self.record_failure()
            raise
        else:
            self.record_success()
            return result
