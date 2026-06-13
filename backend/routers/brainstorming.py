from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from services.brainstorming import generate_brainstorming_ideas

router = APIRouter(tags=["Brainstorming"])

class BrainstormingRequest(BaseModel):
    topic: str
    risk_tolerance: str

class BrainstormIdea(BaseModel):
    title: str
    description: str
    ticker: Optional[str]

class BrainstormingResponse(BaseModel):
    ideas: List[BrainstormIdea]

@router.post("/brainstorm", response_model=BrainstormingResponse)
def brainstorming_endpoint(req: BrainstormingRequest):
    if not req.topic or not req.risk_tolerance:
        raise HTTPException(status_code=400, detail="topic and risk_tolerance are required")
    
    try:
        result = generate_brainstorming_ideas(req.topic, req.risk_tolerance)
        return BrainstormingResponse(
            ideas=result.get("ideas", [])
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
