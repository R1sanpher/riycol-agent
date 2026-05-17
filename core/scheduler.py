"""
Lightweight in-process task scheduler.
No external dependencies. Supports cron-like and interval-based tasks.
"""
import time
import threading
from typing import Callable, Any
from core.logger import log


class ScheduledTask:
    def __init__(self, name: str, fn: Callable, interval_seconds: float = 0,
                 cron: str = "", enabled: bool = True):
        self.name = name
        self.fn = fn
        self.interval = interval_seconds
        self.cron = cron  # Simple: "HH:MM" daily, or "" for interval mode
        self.enabled = enabled
        self.last_run: float = 0
        self.run_count = 0
        self.error_count = 0
        self.last_error: str = ""

    def should_run(self, now: float) -> bool:
        if not self.enabled:
            return False
        if self.interval > 0:
            return (now - self.last_run) >= self.interval
        if self.cron:
            # Simple daily cron: "HH:MM"
            try:
                h, m = map(int, self.cron.split(":"))
                target = h * 3600 + m * 60
                now_time = time.localtime(now)
                now_secs = now_time.tm_hour * 3600 + now_time.tm_min * 60 + now_time.tm_sec
                last_time = time.localtime(self.last_run or 0)
                last_day = last_time.tm_yday
                return now_secs >= target and now_time.tm_yday != last_day
            except Exception:
                return False
        return False

    def snapshot(self) -> dict[str, Any]:
        return {
            "name": self.name, "enabled": self.enabled,
            "interval": self.interval, "cron": self.cron,
            "last_run": self.last_run, "run_count": self.run_count,
            "error_count": self.error_count, "last_error": self.last_error,
        }


class TaskScheduler:
    """Lightweight scheduler that runs tasks in a background daemon thread."""
    def __init__(self, tick_seconds: float = 1.0):
        self._tasks: dict[str, ScheduledTask] = {}
        self._tick = tick_seconds
        self._running = False
        self._thread: threading.Thread | None = None

    def add(self, name: str, fn: Callable, every_seconds: float = 0,
            daily_at: str = "", enabled: bool = True) -> ScheduledTask:
        task = ScheduledTask(name, fn, interval_seconds=every_seconds,
                             cron=daily_at, enabled=enabled)
        self._tasks[name] = task
        log.info(f"Scheduler: added '{name}' "
                 f"{'every ' + str(every_seconds) + 's' if every_seconds else 'daily at ' + daily_at}")
        return task

    def remove(self, name: str):
        self._tasks.pop(name, None)

    def enable(self, name: str): 
        if name in self._tasks:
            self._tasks[name].enabled = True

    def disable(self, name: str):
        if name in self._tasks:
            self._tasks[name].enabled = False

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        log.info("Scheduler: started")

    def stop(self):
        self._running = False
        log.info("Scheduler: stopped")

    def _loop(self):
        while self._running:
            now = time.time()
            for task in list(self._tasks.values()):
                try:
                    if task.should_run(now):
                        task.last_run = now
                        task.run_count += 1
                        task.fn()
                except Exception as e:
                    task.error_count += 1
                    task.last_error = str(e)
                    log.error(f"Scheduler task '{task.name}': {e}")
            time.sleep(self._tick)

    def snapshot(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "task_count": len(self._tasks),
            "tasks": [t.snapshot() for t in self._tasks.values()],
        }

    def run_once(self, name: str):
        """Immediately execute a named task."""
        task = self._tasks.get(name)
        if task:
            try:
                task.last_run = time.time()
                task.run_count += 1
                task.fn()
            except Exception as e:
                task.error_count += 1
                task.last_error = str(e)
                raise


# Global singleton
scheduler = TaskScheduler()
