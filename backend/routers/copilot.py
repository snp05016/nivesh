from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import multiprocessing

from core.security import get_current_user_id, require_auth
from services.copilot_service import process_copilot_request

router = APIRouter(tags=["Copilot"])

class ChatMessage(BaseModel):
    role: str
    content: str

class CopilotRequest(BaseModel):
    user_message: str
    conversation_history: List[ChatMessage] = []
    current_context: Dict[str, Any] = {}

class CopilotResponse(BaseModel):
    reply: str
    context_cards: Optional[List[Dict[str, Any]]] = None

@router.post("/api/v1/copilot/chat", response_model=CopilotResponse)
async def copilot_chat(
    req: CopilotRequest,
    background_tasks: BackgroundTasks,
    user_id: Optional[int] = Depends(get_current_user_id)
):
    """
    Handle chat request. For fast intent resolution, we run it directly.
    For deep analysis, we could spawn a process, but to return the response,
    we'll await the service call which handles the processing.
    """
    try:
        # Pass everything to the service, keeping the router clean.
        result = process_copilot_request(
            user_message=req.user_message,
            conversation_history=[msg.dict() for msg in req.conversation_history],
            current_context=req.current_context,
            user_id=user_id
        )
        return CopilotResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
