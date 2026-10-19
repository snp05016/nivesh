from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from services.brainstorming import generate_brainstorming_ideas
from services.llm_budget import require_llm_budget

router = APIRouter(tags=["Brainstorming"])

class BrainstormingRequest(BaseModel):
    topic: str = Field(max_length=500)
    risk_tolerance: str = Field(max_length=20)

class BrainstormIdea(BaseModel):
    title: str
    description: str
    ticker: Optional[str]

class BrainstormingResponse(BaseModel):
    ideas: List[BrainstormIdea]

@router.post("/brainstorm", response_model=BrainstormingResponse)
def brainstorming_endpoint(req: BrainstormingRequest, user_id: int = Depends(require_llm_budget("brainstorm"))):
    if not req.topic or not req.risk_tolerance:
        raise HTTPException(status_code=400, detail="topic and risk_tolerance are required")
    
    try:
        result = generate_brainstorming_ideas(req.topic, req.risk_tolerance)
        return BrainstormingResponse(
            ideas=result.get("ideas", [])
        )
    except ValueError:
        # The model answered but nothing usable survived validation (LLM-21): retryable, not a 500.
        raise HTTPException(status_code=502, detail="Could not generate ideas, please retry")
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")
