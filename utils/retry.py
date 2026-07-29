import functools
import logging
import time as time_module

logger = logging.getLogger(__name__)


def retry_on_failure(max_attempts: int = 3, delay_seconds: float = 2.0):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as error:
                    last_error = error
                    logger.warning("Attempt %d/%d failed for %s: %s", attempt, max_attempts, func.__name__, error)
                    if attempt < max_attempts:
                        time_module.sleep(delay_seconds)
            raise last_error
        return wrapper
    return decorator