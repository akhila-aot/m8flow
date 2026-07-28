"""Observability middleware for logging and monitoring MCP requests.

This is the single, live observability middleware (a second, unused
duplicate — src/middleware/observability.py — used to exist alongside it;
its useful bits are merged in here and the file is gone).

Wraps every request (it's registered outermost in main.py) to:
- Assign a correlation id and attach it to every log line for the request.
- Log a single allowlisted-shape summary per request: method, tool/resource
  name, duration, outcome, correlation id, tenant id — never raw tool
  arguments or backend bodies (see src/utils/logging.ALLOWED_LOG_FIELDS).
- Detect "swallowed" tool failures: tools return an error envelope instead
  of raising (see src/errors/envelope.py), so a successful call_next() no
  longer means the tool actually succeeded. last_error_outcome carries that
  outcome across without an exception.
- Clear request-scoped context (tenant, tokens, correlation id) in a
  finally block, so nothing can leak into whatever request runs next on
  the same task.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from fastmcp.server.middleware import Middleware, MiddlewareContext

from src.errors.envelope import last_error_outcome
from src.utils.context import clear_context, get_tenant_id, set_correlation_id
from src.utils.logging import get_logger, with_params

logger = get_logger(__name__)


class ObservabilityMiddleware(Middleware):
    """Middleware for logging and monitoring MCP requests."""

    def _base_log_context(self, context: MiddlewareContext[Any], correlation_id: str) -> dict[str, Any]:
        return {
            "method": context.method,
            "tool_name": getattr(context.message, "name", None),
            "correlation_id": correlation_id,
            "tenant_id": get_tenant_id(),
        }

    async def on_message(self, context: MiddlewareContext[Any], call_next: Any) -> Any:
        """Hook for all messages - handles logging, outcome tracking, and context cleanup."""
        correlation_id = str(uuid.uuid4())
        set_correlation_id(correlation_id)
        last_error_outcome.set(None)  # discard any stale value left by a prior request on this task
        start_time = time.time()

        try:
            result = await call_next(context)
            duration_ms = round((time.time() - start_time) * 1000, 2)

            log_data = self._base_log_context(context, correlation_id)
            log_data["duration_ms"] = duration_ms

            # Tools return an error envelope instead of raising, so a clean
            # call_next() doesn't mean the tool call actually succeeded.
            swallowed_error = last_error_outcome.get()
            if swallowed_error is not None:
                log_data["outcome"] = "error"
                log_data["error_category"] = swallowed_error["category"]
                logger.warning("MCP operation completed with an error result", **with_params(log_data))
            else:
                log_data["outcome"] = "success"
                logger.info("MCP operation completed successfully", **with_params(log_data))

            return result

        except Exception:
            duration_ms = round((time.time() - start_time) * 1000, 2)
            log_data = self._base_log_context(context, correlation_id)
            log_data["duration_ms"] = duration_ms
            log_data["outcome"] = "error"

            logger.error("MCP operation failed", exc_info=True, **with_params(log_data))

            # Re-raise to allow error handling middleware/framework to process
            raise

        finally:
            clear_context()
