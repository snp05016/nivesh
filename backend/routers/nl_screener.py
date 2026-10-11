from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from services.nl_screener import NLQueryNotUnderstood, NLQueryUnavailable, process_nl_query

from typing import Dict, List, Optional

router = APIRouter(tags=["Market"])

class NLScreenerRequest(BaseModel):
    query: str = Field(max_length=500)

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
    except NLQueryNotUnderstood:
        raise HTTPException(
            status_code=422,
            detail='Could not understand the query. Try e.g. "banks with PE under 20".',
        )
    except NLQueryUnavailable:
        raise HTTPException(status_code=503, detail="Screener is temporarily unavailable")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")
