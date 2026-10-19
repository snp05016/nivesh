"""Research Lab backend services (docs/platform/api-contract.md, ``/api/v1/research-lab``).

The ml-engine (``/lab/v1``) computes; these services own persistence, ownership,
the trials ledger and LLM use. Every failure is a ``LabError`` carrying the HTTP
status and a client-safe detail, so routers stay thin.
"""
from fastapi import HTTPException


class LabError(HTTPException):
    """A Lab failure with its HTTP status (404 not yours/unknown, 409 limit or
    conflict, 422 rejected by the engine, 503 engine unavailable)."""
