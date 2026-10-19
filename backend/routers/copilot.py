import json
import logging
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Any, Literal, Optional

from core.feature_flags import require_flag
from core.security import require_auth
from services import llm_budget
from services.llm_budget import require_llm_budget
from services.copilot_service import process_copilot_request

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Copilot"])

# LLM-13: the client never builds the system prompt and payloads are bounded.
# A history turn may hold a full assistant reply (Haiku max_tokens 2000 is ~8000 chars).
_MAX_USER_MESSAGE_CHARS = 4000
_MAX_HISTORY_MESSAGE_CHARS = 8000
_MAX_HISTORY_MESSAGES = 20
_MAX_CONTEXT_JSON_CHARS = 8000  # iOS app_navigation is ~3 KB


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., max_length=_MAX_HISTORY_MESSAGE_CHARS)

class CopilotRequest(BaseModel):
    user_message: str = Field(..., min_length=1, max_length=_MAX_USER_MESSAGE_CHARS)
    conversation_history: List[ChatMessage] = Field(default_factory=list, max_length=_MAX_HISTORY_MESSAGES)
    current_context: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("current_context")
    @classmethod
    def _bounded_context(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        if len(json.dumps(v, default=str)) > _MAX_CONTEXT_JSON_CHARS:
            raise ValueError(f"current_context exceeds {_MAX_CONTEXT_JSON_CHARS} characters")
        return v

class CopilotResponse(BaseModel):
    reply: str
    context_cards: Optional[List[Dict[str, Any]]] = None

@router.post("/api/v1/copilot/chat", response_model=CopilotResponse)
def copilot_chat(
    req: CopilotRequest,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(require_llm_budget("copilot"))
):
    """
    Handle chat request. For fast intent resolution, we run it directly.
For deep analysis, we could spawn a process, but to return the response,
we'll await the service call which handles the processing.

    Args:
        req (CopilotRequest): The req.
        background_tasks (BackgroundTasks): The background_tasks.
        user_id (List/Dict): The user_id.

    Returns:
        Any: The response.
    """
    try:
        # Pass everything to the service, keeping the router clean.
        result = process_copilot_request(
            user_message=req.user_message,
            conversation_history=[msg.model_dump() for msg in req.conversation_history],
            current_context=req.current_context,
            user_id=user_id
        )
        return CopilotResponse(**result)
    except Exception:
        logger.exception("copilot chat failed for user %s", user_id)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/v1/ai/allowance")
def ai_allowance(
    user_id: int = Depends(require_auth),
    _flag: None = Depends(require_flag("ai_allowance")),
) -> dict:
    """Today's AI allowance as a percentage and a state; never money, caps or tier."""
    return llm_budget.allowance(user_id)
