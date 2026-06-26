from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.nl_screener import process_nl_query

from typing import Dict, List, Optional

router = APIRouter(tags=["Market"])

class NLScreenerRequest(BaseModel):
    query: str

class NLScreenerResult(BaseModel):
    ticker: str
    company: str
    score: float
    reason: str
    sector: Optional[str] = None

class NLScreenerResponse(BaseModel):
    parsed_filters: Dict[str, str]
    results: List[NLScreenerResult]

@router.post("/api/v1/screener/natural-language", response_model=NLScreenerResponse)
def natural_language_screener(req: NLScreenerRequest):
    """
    Parse a natural language query into structured filters and run screener.

    Args:
        req (NLScreenerRequest): The req.

    Returns:
        Any: The response.
    """
    try:
        return process_nl_query(req.query)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")
