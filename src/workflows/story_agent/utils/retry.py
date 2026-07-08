"""
Retry Utility untuk LLM API Calls
Menangani 429 Resource Exhausted dan error transient lainnya

Utility untuk menangani rate limiting dari Vertex AI / Gemini API
dengan exponential backoff retry mechanism.
"""

import asyncio
import functools
import time
from typing import TypeVar, Callable, Any
import random
from loguru import logger

# Default retry configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 2.0  # seconds
DEFAULT_MAX_DELAY = 60.0  # seconds
DEFAULT_EXPONENTIAL_BASE = 2

T = TypeVar("T")


class RateLimitExceeded(Exception):
    """Raised when rate limit is hit and all retries exhausted."""
    pass


def is_rate_limit_error(exception: Exception) -> bool:
    """
    Check if the exception is a rate limit (429) error.
    
    Mendukung berbagai format error dari Vertex AI / Google API.
    
    Args:
        exception: Exception yang perlu dicek
        
    Returns:
        True jika error adalah rate limit error
    """
    error_str = str(exception).lower()
    
    # Check for common rate limit patterns
    rate_limit_patterns = [
        "429",
        "resource exhausted",
        "resourceexhausted",
        "rate limit",
        "rate_limit",
        "quota exceeded",
        "quota_exceeded",
        "too many requests",
        "requests per minute",
        "tokens per minute",
    ]
    
    return any(pattern in error_str for pattern in rate_limit_patterns)


def is_transient_error(exception: Exception) -> bool:
    """
    Check if the exception is a transient error that should be retried.
    
    Args:
        exception: Exception yang perlu dicek
        
    Returns:
        True jika error adalah transient dan bisa di-retry
    """
    # Check for non-retryable errors first
    error_str = str(exception).lower()
    
    # Event loop closed is NOT retryable - don't retry
    non_retryable_patterns = [
        "event loop is closed",
        "loop is closed",
        "cannot schedule new futures",
    ]
    if any(pattern in error_str for pattern in non_retryable_patterns):
        return False
    
    # Rate limit errors should be retried
    if is_rate_limit_error(exception):
        return True
    
    # Other transient patterns
    transient_patterns = [
        "503",
        "service unavailable",
        "temporarily unavailable",
        "internal server error",
        "500",
        "connection reset",
        "connection timeout",
        "deadline exceeded",
    ]
    
    return any(pattern in error_str for pattern in transient_patterns)


def calculate_backoff_delay(
    attempt: int,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    exponential_base: int = DEFAULT_EXPONENTIAL_BASE,
    jitter: bool = True
) -> float:
    """
    Calculate delay with exponential backoff and optional jitter.
    
    Args:
        attempt: Nomor percobaan (0-indexed)
        base_delay: Delay dasar dalam detik
        max_delay: Delay maksimum dalam detik
        exponential_base: Base untuk exponential backoff
        jitter: Apakah menambahkan random jitter
        
    Returns:
        Delay dalam detik
    """
    # Exponential backoff: base_delay * (exponential_base ^ attempt)
    delay = base_delay * (exponential_base ** attempt)
    
    # Cap at max delay
    delay = min(delay, max_delay)
    
    # Add jitter (0-25% additional random delay)
    if jitter:
        jitter_amount = delay * random.uniform(0, 0.25)
        delay += jitter_amount
    
    return delay


async def retry_async(
    func: Callable[..., T],
    *args,
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    on_retry: Callable[[Exception, int, float], None] = None,
    **kwargs
) -> T:
    """
    Retry an async function with exponential backoff.
    
    Fungsi ini akan mencoba ulang jika terjadi rate limit atau transient error.
    
    Args:
        func: Async function yang akan dijalankan
        *args: Positional arguments untuk func
        max_retries: Jumlah maksimum retry
        base_delay: Delay dasar dalam detik
        max_delay: Delay maksimum dalam detik
        on_retry: Optional callback saat retry (exception, attempt, delay)
        **kwargs: Keyword arguments untuk func
        
    Returns:
        Result dari func
        
    Raises:
        RateLimitExceeded: Jika semua retry gagal karena rate limit
        Exception: Error lain yang tidak bisa di-retry
        
    Example:
        result = await retry_async(
            llm.astream,
            messages,
            max_retries=3,
            base_delay=2.0
        )
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            
            # Check if error should be retried
            if not is_transient_error(e):
                # Non-transient error, raise immediately
                raise
            
            # Check if we've exhausted retries
            if attempt >= max_retries:
                if is_rate_limit_error(e):
                    raise RateLimitExceeded(
                        f"Rate limit exceeded after {max_retries + 1} attempts. "
                        f"Last error: {e}"
                    ) from e
                raise
            
            # Calculate backoff delay
            delay = calculate_backoff_delay(
                attempt=attempt,
                base_delay=base_delay,
                max_delay=max_delay
            )
            
            # Log/notify retry
            if on_retry:
                on_retry(e, attempt + 1, delay)
            else:
                logger.warning(f"Rate limit hit. Retry {attempt + 1}/{max_retries} in {delay:.1f}s...")
            
            # Wait before retry
            await asyncio.sleep(delay)
    
    # Should not reach here, but just in case
    if last_exception:
        raise last_exception


def with_retry(
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
):
    """
    Decorator untuk menambahkan retry logic ke async function.
    
    Args:
        max_retries: Jumlah maksimum retry
        base_delay: Delay dasar dalam detik
        max_delay: Delay maksimum dalam detik
        
    Returns:
        Decorated function dengan retry logic
        
    Example:
        @with_retry(max_retries=3, base_delay=2.0)
        async def call_llm(messages):
            return await llm.astream(messages)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            return await retry_async(
                func,
                *args,
                max_retries=max_retries,
                base_delay=base_delay,
                max_delay=max_delay,
                **kwargs
            )
        return wrapper
    return decorator


async def stream_with_retry(
    llm,
    messages,
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    on_chunk: Callable[[str], None] = None,
):
    """
    Stream LLM response dengan retry logic untuk rate limits.
    
    Khusus untuk streaming responses dari LangChain LLM.
    Jika rate limit terjadi, akan retry dari awal.
    
    Args:
        llm: LangChain LLM instance
        messages: Messages untuk dikirim ke LLM
        max_retries: Jumlah maksimum retry
        base_delay: Delay dasar dalam detik
        max_delay: Delay maksimum dalam detik
        on_chunk: Optional callback untuk setiap chunk
        
    Yields:
        String chunks dari LLM response
        
    Example:
        content = ""
        async for chunk in stream_with_retry(llm, messages, max_retries=3):
            logger.debug(chunk)
            content += chunk
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            # Check if event loop is still running before attempting stream
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                raise RuntimeError("Event loop is closed - cannot stream. This may happen if app was interrupted.")
            
            async for chunk in llm.astream(messages):
                if chunk.content:
                    if on_chunk:
                        on_chunk(chunk.content)
                    yield chunk.content
            # Successfully completed streaming
            return
        except RuntimeError as e:
            # Catch RuntimeError specifically for event loop issues
            if "event loop" in str(e).lower() or "loop is closed" in str(e).lower():
                logger.error(f"Event loop error during streaming: {e}")
                raise  # Don't retry event loop errors
            raise
        except Exception as e:
            last_exception = e
            
            # Check if error should be retried
            if not is_transient_error(e):
                raise
            
            # Check if we've exhausted retries
            if attempt >= max_retries:
                if is_rate_limit_error(e):
                    raise RateLimitExceeded(
                        f"Rate limit exceeded after {max_retries + 1} attempts. "
                        f"Last error: {e}"
                    ) from e
                raise
            
            # Calculate backoff delay
            delay = calculate_backoff_delay(
                attempt=attempt,
                base_delay=base_delay,
                max_delay=max_delay
            )
            
            logger.warning(f"Rate limit hit during streaming. Retry {attempt + 1}/{max_retries} in {delay:.1f}s...")
            
            # Wait before retry
            await asyncio.sleep(delay)
    
    if last_exception:
        raise last_exception


async def invoke_with_retry(
    llm,
    messages,
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
):
    """
    Invoke LLM dengan retry logic untuk rate limits.
    
    Untuk non-streaming LLM calls.
    
    Args:
        llm: LangChain LLM instance
        messages: Messages untuk dikirim ke LLM
        max_retries: Jumlah maksimum retry
        base_delay: Delay dasar dalam detik
        max_delay: Delay maksimum dalam detik
        
    Returns:
        LLM response
        
    Example:
        response = await invoke_with_retry(llm, messages, max_retries=3)
    """
    return await retry_async(
        llm.ainvoke,
        messages,
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=max_delay
    )
