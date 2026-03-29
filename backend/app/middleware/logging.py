# backend/app/middleware/logging.py
"""
Structured JSON logging middleware.
Generates request_id UUID, logs request/response to stdout as JSON.
user_id masked to first 8 characters.
"""

from __future__ import annotations

import json
import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("trustflow.middleware.logging")


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    """
    Starlette middleware that logs every request as structured JSON to stdout.

    Log fields: timestamp, level, service, request_id, user_id (first 8 chars),
    expense_id (if present), event, duration_ms, status_code.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process the request with structured logging."""
        request_id = str(uuid.uuid4())
        start_time = time.time()

        # Attach request_id to the request state for downstream use
        request.state.request_id = request_id

        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = int((time.time() - start_time) * 1000)
            self._log_request(
                request=request,
                request_id=request_id,
                status_code=500,
                duration_ms=duration_ms,
                event="request_error",
            )
            raise

        duration_ms = int((time.time() - start_time) * 1000)

        # Add request_id to response headers
        response.headers["X-Request-ID"] = request_id

        # Log the request
        self._log_request(
            request=request,
            request_id=request_id,
            status_code=response.status_code,
            duration_ms=duration_ms,
            event="request_completed",
        )

        return response

    def _log_request(
        self,
        request: Request,
        request_id: str,
        status_code: int,
        duration_ms: int,
        event: str,
    ) -> None:
        """Emit a structured JSON log entry to stdout."""
        from datetime import datetime, timezone

        # Extract user_id from request state (set by auth middleware)
        user_id = None
        if hasattr(request.state, "user_id"):
            user_id = request.state.user_id

        # Extract expense_id from path if present
        expense_id = None
        path = request.url.path
        if "/expenses/" in path:
            parts = path.split("/expenses/")
            if len(parts) > 1:
                expense_id = parts[1].split("/")[0]

        # Mask user_id to first 8 chars
        masked_user_id = user_id[:8] if user_id else None

        log_entry = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "level": "INFO" if status_code < 400 else "WARN" if status_code < 500 else "ERROR",
            "service": "trustflow-api",
            "request_id": request_id,
            "method": request.method,
            "path": path,
            "user_id": masked_user_id,
            "expense_id": expense_id,
            "event": event,
            "duration_ms": duration_ms,
            "status_code": status_code,
        }

        # Remove None values for cleaner output
        log_entry = {k: v for k, v in log_entry.items() if v is not None}

        # Log level based on status code
        level = logging.INFO if status_code < 400 else logging.WARNING if status_code < 500 else logging.ERROR
        logger.log(level, json.dumps(log_entry))
