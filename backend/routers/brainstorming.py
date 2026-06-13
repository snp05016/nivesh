from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from database import get_session
from sqlalchemy.orm import Session
from services.llm_utils import _deepseek_chat

router = APIRouter(prefix="/brainstorm", tags=["Brainstorming"])

class BrainstormRequest(BaseModel):
    topic: str
    risk_tolerance: str

class BrainstormIdea(BaseModel):
    title: str
    description: str
    ticker: Optional[str]

class BrainstormResponse(BaseModel):
    ideas: List[BrainstormIdea]

@router.post("", response_model=BrainstormResponse)
def brainstorm(req: BrainstormRequest):
    prompt = f"""
    You are an expert Indian stock market advisor.
    The user is brainstorming investment ideas about the topic: "{req.topic}".
    Their risk tolerance is "{req.risk_tolerance}".

    Generate a JSON object with a single key "ideas" containing a list of 3-5 distinct, actionable investment strategies or angles related to this topic in the Indian market.
    Each idea should be an object with:
    - "title": A short catchy title (e.g. "EV Battery Infrastructure")
    - "description": A 1-2 sentence description of why this angle works.
    - "ticker": (Optional) An NSE/BSE stock ticker symbol that perfectly fits this idea (e.g. "RELIANCE").

    Return ONLY valid JSON.
    """
    
    try:
        raw_res = _deepseek_chat(prompt, max_tokens=800)
        import json
        import re
        
        # Extract JSON from potential markdown blocks
        match = re.search(r'\{.*\}', raw_res, re.DOTALL)
        if match:
            raw_res = match.group(0)
            
        data = json.loads(raw_res)
        ideas_raw = data.get("ideas", [])
        
        if not ideas_raw:
            raise ValueError("LLM returned empty data")
            
        ideas = []
        for i in ideas_raw:
            ideas.append(BrainstormIdea(
                title=i.get("title", "Idea"),
                description=i.get("description", ""),
                ticker=i.get("ticker")
            ))
            
        return BrainstormResponse(ideas=ideas)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
