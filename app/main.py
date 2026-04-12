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
from pages.technical_visualization import technical_analysis_page
from apis.routes import router as api_router

# Database URL
DATABASE_URL = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"

# --- FastAPI Setup ---
api_app = FastAPI(title="Stock Analysis API")

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

# Main app
def main():
    # Set wide layout and custom CSS
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
            /* Hide the automatic navigation list from the pages/ directory */
            /* This ensures only the legacy selectbox is used for navigation */
            [data-testid="stSidebarNav"] {
                display: none;
            }
        </style>
    """, unsafe_allow_html=True)

    # App title and page selection
    st.title("Stock Analysis App")
    page = st.sidebar.selectbox("Select Page", ["Data", "Result", "Analyze", "Suggestion", "Technical Analyze"], index=0)

    # --- Revamped State Clearing Logic ---
    # Track the previous page to detect a page switch
    if 'previous_page' not in st.session_state:
        st.session_state['previous_page'] = page

    # Only clear the session state when switching AWAY from Technical Analyze
    if st.session_state['previous_page'] == "Technical Analyze" and page != "Technical Analyze":
        st.session_state.clear()
    
    st.session_state['previous_page'] = page

    if page == "Data":       
        data_page(engine)
    elif page == "Result":
        result_page(engine)
    elif page == "Analyze":
        analyze_page(engine)
    elif page == "Suggestion":
        suggestion_page(engine)
    elif page == "Technical Analyze":
        technical_analysis_page(engine)

if __name__ == "__main__":
    main()