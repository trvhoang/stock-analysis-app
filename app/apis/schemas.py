from pydantic import BaseModel
from typing import Optional, List

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

class SuggestionTickerPossibility(BaseModel):
    """
    Represents a ticker ranked by statistical probability of an Up move.
    """
    ticker: str
    possibility_up: float
    total_signals: int

class SuggestionTickerDelta(BaseModel):
    """
    Represents a ticker ranked by its historical maximum price increase.
    """
    ticker: str
    max_up_delta: float
    total_signals: int

class SuggestionAPIResponse(BaseModel):
    """
    Structured response for market-wide suggestions, 
    focusing exclusively on bullish 'Up' opportunities.
    """
    top_possibility_up: List[SuggestionTickerPossibility]
    top_delta_up: List[SuggestionTickerDelta]