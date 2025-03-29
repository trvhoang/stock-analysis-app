import streamlit as st
from dotenv import load_dotenv
import os
from data_preparation import data_page, get_engine_with_retry, init_db
from result_visualization import result_page
from analyze_visualization import analyze_page
from suggestion_visualization import suggestion_page

# Load environment variables
load_dotenv()

# Database URL
DATABASE_URL = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"

# Main app
def main():
    # Set wide layout and custom CSS
    st.set_page_config(layout="wide")
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

    # Initialize database connection
    engine = get_engine_with_retry(DATABASE_URL)
    init_db(engine)

    # App title and page selection
    st.title("Stock Analysis App")
    page = st.sidebar.selectbox("Select Page", ["Data", "Result", "Analyze", "Suggestion"], index=0)

    # Route to appropriate page
    if page == "Data":
        data_page(engine)
    elif page == "Result":
        result_page(engine)
    elif page == "Analyze":
        analyze_page(engine)
    elif page == "Suggestion":
        suggestion_page(engine)

if __name__ == "__main__":
    main()