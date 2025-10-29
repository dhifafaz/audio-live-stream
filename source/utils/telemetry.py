import time
import asyncio
from functools import wraps
from eb_labs.utils.log import logger
from config import settings


def logging(func):
    """
    A decorator that logs function calls for both synchronous and asynchronous functions.
    
    Features:
    - Logs function entry with function name (including class name if applicable)
    - Logs function completion with execution time
    - Works with both sync and async functions
    - Supports methods in classes
    
    Args:
        func (callable): The function to be decorated
    
    Returns:
        callable: Wrapped function with logging
    """
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        class_name = ''
        if args and hasattr(args[0], '__class__'):
            class_name = f"{args[0].__class__.__name__}."

        logger.info(f"Calling async function `{class_name}{func.__name__}`")
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            logger.info(f"Async function `{class_name}{func.__name__}` completed with execution time: {round(time.time() - start_time, 2)}")
            return result
        except Exception as e:
            logger.error(f"Async function `{class_name}{func.__name__}` failed: {e}")
            raise

    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        class_name = ''
        if args and hasattr(args[0], '__class__'):
            class_name = f"{args[0].__class__.__name__}."

        logger.info(f"Calling function `{class_name}{func.__name__}`")
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            logger.info(f"Function `{class_name}{func.__name__}` completed with execution time: {round(time.time() - start_time, 2)}")
            return result
        except Exception as e:
            logger.error(f"Function `{class_name}{func.__name__}` failed: {e}")
            raise

    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper