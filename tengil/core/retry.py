"""Retry decorator for network operations with exponential backoff."""
import time
import functools
from typing import Tuple, Type
from tengil.core.logger import get_logger

logger = get_logger(__name__)


def retry(
    max_attempts: int = 3,
    delay: float = 2.0,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
    """Retry decorator with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay in seconds between retries
        backoff: Backoff multiplier for each retry
        exceptions: Tuple of exception types to catch and retry

    Example:
        @retry(max_attempts=3, delay=5, exceptions=(subprocess.CalledProcessError,))
        def download_template(template):
            # Network operation that might fail
            ...
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_attempts:
                        logger.error(
                            f"{func.__name__} failed after {max_attempts} attempts: {e}"
                        )
                        raise

                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt}/{max_attempts}): {e}"
                    )
                    logger.info(f"Retrying in {current_delay:.1f}s...")
                    time.sleep(current_delay)
                    current_delay *= backoff

            return None

        return wrapper

    return decorator
