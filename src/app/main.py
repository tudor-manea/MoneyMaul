"""Main Streamlit application entry point."""

import streamlit as st

from .pages import team_builder

# Page configuration
st.set_page_config(
    page_title="MoneyMaul - Six Nations Fantasy",
    page_icon="🏉",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Navigation
PAGES = {
    "Team Builder": team_builder,
}


def main() -> None:
    """Run the main application."""
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
