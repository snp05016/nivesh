from fastapi import APIRouter, Depends, HTTPException
from database import get_session, AnalysisHistory
from sqlalchemy import func

router = APIRouter(prefix="/portfolio", tags=["Portfolio"])

@router.get("/signal-accuracy")
def get_signal_accuracy():
    with get_session() as db:
        results = db.query(
            AnalysisHistory.signal,
            func.count(AnalysisHistory.id).label('total'),
            func.sum(func.cast(AnalysisHistory.was_correct, Integer)).label('correct') # SQLite bools are 0/1 but better check
        ).filter(AnalysisHistory.was_correct != None).group_by(AnalysisHistory.signal).all()
        
        # ... logic to return {signal: 'BUY', total: N, correct: M, accuracy_pct: P}
