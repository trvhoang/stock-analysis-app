from fastapi import APIRouter, Request, HTTPException, BackgroundTasks, Query
from apis.schemas import (
    TickerAnalysisResponse, DataPreparationResponse, 
    SuggestionAPIResponse, SuggestionTickerPossibility, 
    SuggestionTickerDelta
)
from commons.common_functions import analyze_ticker, synthesize_all_advice, get_all_tickers
from pages.data_preparation import run_full_ingestion, get_default_report_date, data_prep_lock
from typing import Optional, List
from datetime import datetime
import pandas as pd
import concurrent.futures

router = APIRouter()

@router.get("/analyze/{ticker}", response_model=TickerAnalysisResponse, summary="Analyze Single Ticker")
async def trigger_ticker_analyze(
    ticker: str, 
    request: Request, 
    validation_days: int = Query(5, description="The lookback window (trading days) to identify the current price signal."), 
    result_days: int = Query(5, description="The lookforward window (trading days) to predict future outcomes.")
):
    """
    Triggers a comprehensive statistical and technical analysis for a specific stock ticker.
    Returns a synthesized advice object combining historical probabilities and technical indicator trends.
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

@router.get("/suggestions", response_model=SuggestionAPIResponse, summary="Get Market Suggestions")
async def get_suggestions(
    request: Request,
    day_range: int = Query(5, description="The validation period (trading days) used to calculate the current price delta."),
    result_day_range: int = Query(5, description="The lookforward period (trading days) used to evaluate historical success."),
    min_avg_volume: int = Query(1000000, description="Minimum average volume threshold for liquidity filtering (default 1M shares)."),
    year_gap: int = Query(1, description="Number of years of history to verify ticker activity and continuity.")
):
    """
    Scans the market for the top 5 high-probability bullish opportunities.
    
    - **Filtering**: Only suggests tickers where Statistical and Technical trends are both 'Up'.
    - **Multi-tier Sorting**: 
        1. **Metric**: Ranked by Probability % or Max Delta %.
        2. **Signal Count**: Higher historical frequency ranks higher.
        3. **Exchange**: Priority order HSX > HNX > UPCOM.
    - **Exclusions**: This endpoint focuses exclusively on 'Up' (bullish) suggestions.
    """
    engine = request.app.state.engine
    
    # 1. Discover liquid/active tickers
    tickers = get_all_tickers(engine, min_avg_volume, year_gap)
    
    if not tickers:
        return SuggestionAPIResponse(top_possibility_up=[], top_delta_up=[])

    # 2. Parallel analysis across all tickers
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        future_to_ticker = {
            executor.submit(analyze_ticker, t, day_range, result_day_range, engine): t 
            for t in tickers
        }
        for future in concurrent.futures.as_completed(future_to_ticker):
            res = future.result()
            if res:
                results.append(res)
                
    if not results:
        return SuggestionAPIResponse(top_possibility_up=[], top_delta_up=[])

    # 3. Process rankings using Parity Logic with UI
    df = pd.DataFrame(results)
    
    # Map exchange to numerical rank for sorting (HSX: 3, HNX: 2, UPCOM: 1)
    ex_map = {"HSX": 3, "HNX": 2, "UPCOM": 1}
    df["ex_rank"] = df["exchange"].map(ex_map).fillna(0)

    # Bullish filter: Stat Trend must be Up AND Technical Trend must be bullish
    bullish_tech = ["Strong Up", "Up", "Overbought (Up)"]
    df_up = df[
        df["stat_trend"].isin(["Strong Up", "Up"]) & 
        df["tech_trend"].isin(bullish_tech)
    ]

    # Top 5 by Possibility (Primary: possibility_up)
    top_possibility = df_up.sort_values(
        by=["possibility_up", "total_signals", "ex_rank"], 
        ascending=[False, False, False]
    ).head(5)

    # Top 5 by Delta (Primary: max_up_delta)
    top_delta = df_up.sort_values(
        by=["max_up_delta", "total_signals", "ex_rank"], 
        ascending=[False, False, False]
    ).head(5)

    # 4. Construct response
    return SuggestionAPIResponse(
        top_possibility_up=[
            SuggestionTickerPossibility(
                ticker=row['ticker'], 
                possibility_up=row['possibility_up'], 
                total_signals=row['total_signals']
            ) for _, row in top_possibility.iterrows()
        ],
        top_delta_up=[
            SuggestionTickerDelta(
                ticker=row['ticker'], 
                max_up_delta=row['max_up_delta'], 
                total_signals=row['total_signals']
            ) for _, row in top_delta.iterrows()
        ]
    )

@router.post("/prepare-data", response_model=DataPreparationResponse, summary="Trigger Data Ingestion")
async def trigger_data_preparation(
    background_tasks: BackgroundTasks,
    request: Request,
    report_date: Optional[str] = Query(None, description="The reference date for data (YYYY-MM-DD). Defaults to latest trading date."),
    years: int = Query(1, description="Number of years of historical data to download and process.")
):
    """
    Triggers a background task to download and ingest historical market data from external sources.
    This process is thread-safe and locked to prevent concurrent execution.
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