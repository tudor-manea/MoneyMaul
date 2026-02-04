"""Main Streamlit application entry point."""

import sys
from pathlib import Path

# Add project root to path for direct execution
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import streamlit as st

from src.app.pages import team_builder

# Navigation
PAGES = {
    "Team Builder": team_builder,
}


def main() -> None:
    """Run the main application."""
    st.set_page_config(
        page_title="MoneyMaul - Six Nations Fantasy",
        page_icon="🏉",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.sidebar.title("MoneyMaul")
    st.sidebar.markdown("*Six Nations Fantasy Assistant*")
    st.sidebar.divider()

    # Page selection
    page_name = st.sidebar.radio("Navigation", list(PAGES.keys()), label_visibility="collapsed")

    # Run selected page
    page = PAGES[page_name]
    page.render()


if __name__ == "__main__":
    main()
