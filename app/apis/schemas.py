from pydantic import BaseModel
from typing import Optional

class TickerAnalysisResponse(BaseModel):
    """
    Structured response for a single ticker analysis request.
    """
    ticker: str
    signal: str            # Current X-Day Delta with dates
    statistical_advice: str # Probability-based prediction string
    technical_advice: str   # Overall trend and score string
    final_advice: str       # Combined decision matrix advice

class DataPreparationResponse(BaseModel):
    """
    Response model for data preparation trigger.
    """
    status: str             # "accepted", "busy", or "error"
    message: str            # Descriptive status message
    detail: Optional[str] = None # Additional information (e.g., date used)