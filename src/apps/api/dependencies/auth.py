"""
API Key Authentication Dependency
Validates X-API-Key header for protected endpoints.
"""

import os

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from loguru import logger

# Header scheme: expects "X-API-Key" header
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

_DUMMY_PROD_API_KEY = "dummy"


def get_api_key() -> str:
    """Get the configured API key from environment."""
    key = os.getenv("API_KEY", "")
    if not key:
        if os.getenv("VERCEL"):
            logger.warning(
                "[AUTH::PERINGATAN] API_KEY not set; using dummy key for Vercel"
            )
            return _DUMMY_PROD_API_KEY
        logger.warning("[AUTH::PERINGATAN] API_KEY not set in environment")
    return key


async def verify_api_key(
    provided_key: str = Depends(api_key_header),
) -> str:
    """
    Validate the API key from the request header.
    Returns the key if valid, raises 401 if invalid.
    """
    expected_key = get_api_key()

    if not expected_key:
        logger.error("[AUTH::GALAT] API_KEY not configured on server")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server API key not configured",
        )

    if provided_key != expected_key:
        logger.warning("[AUTH::DITOLAK] Invalid API key attempt")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "APIKey"},
        )

    return provided_key
