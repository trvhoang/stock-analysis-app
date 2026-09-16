import streamlit as st

# Must be the first Streamlit command called to avoid StreamlitAPIException
st.set_page_config(layout="wide")

from dotenv import load_dotenv
import os

# Load environment variables immediately to ensure they are available 
# for all subsequent imports (e.g., database URLs, Numba cache paths)
load_dotenv()

import threading
import uvicorn
from fastapi import FastAPI
from pages.data_preparation import data_page, get_engine_with_retry, init_db
from pages.result_visualization import result_page
from pages.analyze_visualization import analyze_page
from pages.suggestion_visualization import suggestion_page
from pages.technical_visualization import (
    clear_technical_session_state,
    technical_analysis_page,
)
from pages.backtest_lab import render_backtest_page
from pages.flexible_rulebook import render_flexible_rulebook_page
from backtest_engine.pipeline import run_backtest_batch_from_env
from apis.routes import router as api_router

# Database URL
DATABASE_URL = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"

# --- FastAPI Setup ---
def _create_api_app() -> FastAPI:
    # Streamlit 1.62 treats a direct top-level FastAPI(...) assignment as the
    # primary ASGI app. Indirection keeps this entrypoint in dashboard mode.
    return FastAPI(title="Stock Analysis API")


api_app = _create_api_app()

@st.cache_resource
def initialize_global_services():
    """
    Initializes global resources (DB engine, API server) once per app lifecycle.
    """
    # Initialize database engine for shared use
    engine = get_engine_with_retry(DATABASE_URL)
    init_db(engine)

    # Configure FastAPI
    api_app.state.engine = engine
    api_app.include_router(api_router, prefix="/api")

    # Start FastAPI in a background thread
    thread = threading.Thread(
        target=lambda: uvicorn.run(api_app, host="0.0.0.0", port=3500, log_level="info"), 
        daemon=True
    )
    thread.start()
    return engine

engine = initialize_global_services()

def build_navigation_pages(engine):
    """Return the app's stable, flat top-navigation routes."""
    return [
        st.Page(
            lambda: data_page(engine),
            title="Data",
            icon=":material/database:",
            url_path="data",
            default=True,
        ),
        st.Page(
            lambda: result_page(engine),
            title="Result",
            icon=":material/leaderboard:",
            url_path="result",
        ),
        st.Page(
            lambda: analyze_page(engine),
            title="Analyze",
            icon=":material/query_stats:",
            url_path="analyze",
        ),
        st.Page(
            lambda: suggestion_page(engine),
            title="Suggestion",
            icon=":material/lightbulb:",
            url_path="suggestion",
        ),
        st.Page(
            lambda: technical_analysis_page(engine),
            title="Technical Analyze",
            icon=":material/candlestick_chart:",
            url_path="technical-analyze",
        ),
        st.Page(
            lambda: render_backtest_page(
                engine=engine,
                engine_factory=run_backtest_batch_from_env,
            ),
            title="Backtest",
            icon=":material/science:",
            url_path="backtest",
        ),
        st.Page(
            lambda: render_flexible_rulebook_page(engine),
            title="Flexible Rulebook",
            icon=":material/tune:",
            url_path="flexible-rulebook",
        ),
    ]


# Main app
def main():
    # Keep page content wide while leaving page ownership to each renderer.
    st.markdown("""
        <style>
            .main .block-container {
                padding-left: 1rem;
                padding-right: 1rem;
                max-width: 95%;
            }
            .sidebar .sidebar-content {
                padding: 1rem;
            }
            [data-testid="stDataframe"] {
                width: 100% !important;
            }
        </style>
    """, unsafe_allow_html=True)

    selected_page = st.navigation(build_navigation_pages(engine), position="top")
    selected_title = selected_page.title
    if (
        st.session_state.get("previous_page") == "Technical Analyze"
        and selected_title != "Technical Analyze"
    ):
        clear_technical_session_state(st.session_state)
    st.session_state["previous_page"] = selected_title
    selected_page.run()

if __name__ == "__main__":
    main()
