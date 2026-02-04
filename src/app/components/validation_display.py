"""Validation display component for showing team validation results."""

import streamlit as st

from ...analysis import ValidationResult


def render_validation(result: ValidationResult) -> None:
    """
    Render validation results with errors and warnings.

    Args:
        result: Validation result to display.
    """
    if result.is_valid and not result.warnings:
        st.success("Team is valid!")
        return

    # Show errors
    if result.errors:
        st.subheader("Issues")
        for error in result.errors:
            st.error(f"❌ {error.message}")

    # Show warnings
    if result.warnings:
        st.subheader("Warnings")
        for warning in result.warnings:
            st.warning(f"⚠️ {warning}")
