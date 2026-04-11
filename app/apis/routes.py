from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from apis.schemas import TickerAnalysisResponse, DataPreparationResponse
from commons.common_functions import analyze_ticker, synthesize_all_advice
from pages.data_preparation import run_full_ingestion, get_default_report_date, data_prep_lock
from typing import Optional
from datetime import datetime

router = APIRouter()

@router.get("/analyze/{ticker}", response_model=TickerAnalysisResponse)
async def trigger_ticker_analyze(ticker: str, request: Request, validation_days: int = 5, result_days: int = 5):
    """
    Trigger a full analysis for a specific ticker.
    Returns statistical and technical advice in a formatted JSON object.
    """
    # Retrieve the shared SQLAlchemy engine from the FastAPI app state
    engine = request.app.state.engine
    
    # Perform the core statistical analysis
    # analyze_ticker returns dict with current_delta, start_date, end_date, and possibilities
    stats_data = analyze_ticker(ticker.upper(), validation_days, result_days, engine)
    
    if not stats_data:
        raise HTTPException(status_code=404, detail=f"Data for ticker '{ticker}' not found or insufficient.")

    # Synthesize the strings for the response
    # This function is implemented in commons/common_functions.py to ensure 
    # consistency between the API and the Streamlit UI.
    advice = synthesize_all_advice(stats_data, validation_days, result_days, engine)
    
    # Construct the JSON response object
    # Formatting dates to dd/mm/yyyy as per request requirements
    start_str = stats_data['start_date'].strftime("%d/%m/%Y")
    end_str = stats_data['end_date'].strftime("%d/%m/%Y")
    signal_str = f"Current {validation_days}-Day Delta: {stats_data['current_delta']}% ({start_str} - {end_str})"

    return TickerAnalysisResponse(
        ticker=ticker.upper(),
        signal=signal_str,
        statistical_advice=advice['statistical'],
        technical_advice=advice['technical'],
        final_advice=advice['final']
    )

@router.post("/prepare-data", response_model=DataPreparationResponse)
async def trigger_data_preparation(
    background_tasks: BackgroundTasks,
    request: Request,
    report_date: Optional[str] = None,
    years: int = 1
):
    """
    Trigger the data preparation process (download and ingestion).
    If report_date is not provided, uses the latest trading date.
    """
    if data_prep_lock.locked():
        return DataPreparationResponse(
            status="busy",
            message="A data preparation task is already in progress. Please try again later."
        )

    # Determine the date to use
    try:
        parsed_date = datetime.strptime(report_date, "%Y-%m-%d").date() if report_date else get_default_report_date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format for report_date. Use YYYY-MM-DD.")

    engine = request.app.state.engine
    
    # Run the long-running ingestion process in a background task to avoid timeouts
    background_tasks.add_task(run_full_ingestion, parsed_date, years, engine)

    return DataPreparationResponse(
        status="accepted",
        message="Data preparation task has been started in the background.",
        detail=f"Using report_date: {parsed_date}, years: {years}"
    )