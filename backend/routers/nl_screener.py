from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.nl_screener import process_nl_query

router = APIRouter(tags=["Market"])

class NLScreenerRequest(BaseModel):
    query: str

@router.post("/api/v1/screener/natural-language")
def natural_language_screener(req: NLScreenerRequest):
    """
    Parse a natural language query into structured filters and run screener.
    """
    try:
        return process_nl_query(req.query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
