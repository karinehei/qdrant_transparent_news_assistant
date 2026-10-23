"""Middleware for rate limiting, CORS, and request logging."""

from __future__ import annotations

import logging
import time
import uuid
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from fastapi import Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Simple in-memory rate limiter (use Redis in production)
_rate_limit_store: dict[str, list[datetime]] = defaultdict(list)
_rate_limit_window = timedelta(seconds=60)
_rate_limit_max_requests = 100


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple rate limiting middleware."""

    async def dispatch(self, request: Request, call_next: Callable):
        # Get client identifier (IP address)
        client_id = request.client.host if request.client else "unknown"

        # Clean old entries
        now = datetime.now(UTC)
        _rate_limit_store[client_id] = [ts for ts in _rate_limit_store[client_id] if now - ts < _rate_limit_window]

        # Check rate limit
        if len(_rate_limit_store[client_id]) >= _rate_limit_max_requests:
            return Response(
                content="Rate limit exceeded",
                status_code=429,
                headers={"Retry-After": "60"},
            )

        # Record request
        _rate_limit_store[client_id].append(now)

        response = await call_next(request)
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Structured logging middleware with request IDs."""

    async def dispatch(self, request: Request, call_next: Callable):
        # Generate request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Log request
        start_time = time.time()
        logger.info(
            f"request_started request_id={request_id} method={request.method} path={request.url.path}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "client_ip": request.client.host if request.client else None,
            },
        )

        try:
            response = await call_next(request)
            latency_ms = (time.time() - start_time) * 1000

            logger.info(
                f"request_completed request_id={request_id} status={response.status_code} latency_ms={latency_ms:.2f}",
                extra={
                    "request_id": request_id,
                    "status_code": response.status_code,
                    "latency_ms": latency_ms,
                },
            )

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            return response

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.exception(
                f"request_error request_id={request_id} latency_ms={latency_ms:.2f}",
                extra={
                    "request_id": request_id,
                    "error": str(e),
                    "latency_ms": latency_ms,
                },
            )
            raise


def setup_cors(app):
    """Configure CORS for the application."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
        ],  # Common dev ports
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["*"],
    )
