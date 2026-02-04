"""Team status component showing budget and constraints."""

import streamlit as st

from ...models import Team, Country, MAX_BUDGET, MAX_PER_COUNTRY, MIN_SQUAD_SIZE, MAX_SQUAD_SIZE
from ...analysis import get_squad_slots_remaining, get_available_slots_for_country


def render_team_status(team: Team) -> None:
    """
    Render team status metrics.

    Args:
        team: The team to display status for.
    """
    # Budget meter
    budget_used = team.total_value
    budget_remaining = team.budget_remaining
    budget_pct = (budget_used / MAX_BUDGET) * 100

    st.metric(
        label="Budget",
        value=f"⭐ {budget_remaining:.1f}",
        delta=f"{budget_used:.1f} / {MAX_BUDGET} used",
        delta_color="off",
    )

    st.progress(min(budget_pct / 100, 1.0))

    # Squad size
    squad_size = team.squad_size
    slots_remaining = get_squad_slots_remaining(team)

    col1, col2 = st.columns(2)
    with col1:
        st.metric(
            label="Squad Size",
            value=f"{squad_size} / {MAX_SQUAD_SIZE}",
            delta=f"{slots_remaining} slots" if slots_remaining > 0 else "Full",
            delta_color="normal" if squad_size >= MIN_SQUAD_SIZE else "off",
        )

    with col2:
        # Status indicator
        if squad_size >= MIN_SQUAD_SIZE:
            st.success("Squad complete")
        else:
            needed = MIN_SQUAD_SIZE - squad_size
            st.warning(f"Need {needed} more player{'s' if needed > 1 else ''}")

    # Country breakdown
    with st.expander("Country breakdown", expanded=False):
        country_counts = team.country_counts
        for country in Country:
            count = country_counts.get(country, 0)
            slots = get_available_slots_for_country(team, country)
            bar_pct = count / MAX_PER_COUNTRY

            col1, col2 = st.columns([3, 1])
            with col1:
                st.progress(bar_pct, text=f"{country.value}: {count}/{MAX_PER_COUNTRY}")
            with col2:
                if slots == 0:
                    st.caption("Full")
                else:
                    st.caption(f"{slots} left")
