"""Tests for core/retry.py — RetryPolicy, retry decorator, CircuitBreaker."""
import time, pytest
from core.retry import RetryPolicy, retry, CircuitBreaker, CircuitOpenError


class TestRetryPolicy:
    def test_policy_defaults(self):
        p = RetryPolicy()
        assert p.max_attempts == 3
        assert p.base_delay == 1.0
        assert p.max_delay == 30.0
        assert p.backoff == 2.0
        assert p.jitter is True

    def test_policy_custom(self):
        p = RetryPolicy(max_attempts=5, base_delay=0.5, retryable_exceptions=(ValueError,))
        assert p.max_attempts == 5
        assert p.base_delay == 0.5
        assert ValueError in p.retryable_exceptions


class TestRetryDecorator:
    def test_retry_succeeds_first_attempt(self):
        call_count = [0]

        @retry(max_attempts=3, base_delay=0.01)
        def f():
            call_count[0] += 1
            return "ok"

        assert f() == "ok"
        assert call_count[0] == 1

    def test_retry_succeeds_on_third_attempt(self):
        call_count = [0]

        @retry(max_attempts=3, base_delay=0.01)
        def f():
            call_count[0] += 1
            if call_count[0] < 3:
                raise ConnectionError("transient")
            return "ok"

        assert f() == "ok"
        assert call_count[0] == 3

    def test_retry_exceeds_max_attempts(self):
        @retry(max_attempts=3, base_delay=0.01, retryable=(ConnectionError,))
        def f():
            raise ConnectionError("always fail")

        with pytest.raises(ConnectionError):
            f()

    def test_retry_non_retryable_exception(self):
        call_count = [0]

        @retry(max_attempts=3, base_delay=0.01, retryable=(ConnectionError,))
        def f():
            call_count[0] += 1
            raise ValueError("not retryable")

        with pytest.raises(ValueError):
            f()
        assert call_count[0] == 1  # no retries for ValueError

    def test_retry_backoff_timing(self):
        delays = []

        @retry(max_attempts=4, base_delay=0.01, jitter=False)
        def f():
            delays.append(time.monotonic())
            raise ConnectionError("fail")

        try:
            f()
        except ConnectionError:
            pass
        assert len(delays) == 4
        for i in range(1, len(delays)):
            gap = delays[i] - delays[i - 1]
            expected = 0.01 * (2 ** (i - 1))
            assert abs(gap - expected) < 0.15  # allow timing variance

    def test_retry_preserves_function_metadata(self):
        @retry(max_attempts=3)
        def my_func(x: int) -> str:
            """Docstring."""
            return str(x)

        assert my_func.__name__ == "my_func"
        assert "Docstring" in my_func.__doc__ or "Docstring" in (my_func.__doc__ or "")


class TestCircuitBreaker:
    def test_initial_state_closed(self):
        cb = CircuitBreaker("test")
        assert cb.state == "closed"
        assert cb.is_open is False

    def test_closed_to_open_after_failures(self):
        cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=60)
        for _ in range(3):
            try:
                cb.call(lambda: (_ for _ in ()).throw(ConnectionError("fail")))
            except ConnectionError:
                pass
        assert cb.state == "open"
        assert cb.is_open is True

    def test_half_open_after_recovery_timeout(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.05)
        try:
            cb.call(lambda: (_ for _ in ()).throw(ConnectionError("fail")))
        except ConnectionError:
            pass
        assert cb.state == "open"
        time.sleep(0.1)
        assert cb.state == "half_open"
        assert cb.is_open is False

    def test_half_open_to_closed_on_success(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.05,
                           half_open_limit=1)
        try:
            cb.call(lambda: (_ for _ in ()).throw(ConnectionError("fail")))
        except ConnectionError:
            pass
        time.sleep(0.1)
        assert cb.state == "half_open"
        result = cb.call(lambda: "success")
        assert result == "success"
        assert cb.state == "closed"

    def test_half_open_to_open_on_failure(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.05,
                           half_open_limit=1)
        try:
            cb.call(lambda: (_ for _ in ()).throw(ConnectionError("fail")))
        except ConnectionError:
            pass
        time.sleep(0.1)
        assert cb.state == "half_open"
        try:
            cb.call(lambda: (_ for _ in ()).throw(ConnectionError("fail again")))
        except ConnectionError:
            pass
        assert cb.state == "open"

    def test_circuit_open_error_raised(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=60)
        try:
            cb.call(lambda: (_ for _ in ()).throw(ConnectionError("fail")))
        except ConnectionError:
            pass
        assert cb.state == "open"
        with pytest.raises(CircuitOpenError) as exc:
            cb.call(lambda: "should not be called")
        assert "open" in str(exc.value)

    def test_record_success_resets_counter(self):
        cb = CircuitBreaker("test", failure_threshold=5)
        for _ in range(4):
            try:
                cb.call(lambda: (_ for _ in ()).throw(ConnectionError()))
            except ConnectionError:
                pass
        cb.record_success()
        assert cb.state == "closed"

    def test_concurrent_calls(self):
        import threading
        cb = CircuitBreaker("test", failure_threshold=20)
        errors = []

        def call():
            try:
                return cb.call(lambda: "ok")
            except CircuitOpenError as e:
                errors.append(e)

        threads = [threading.Thread(target=call) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0
        assert cb.state == "closed"
