"""Player table component for displaying and selecting players."""

from typing import Callable, Optional

import streamlit as st

from ...models import Player, Team
from ...analysis import can_add_player


def render_player_table(
    players: list[Player],
    team: Team,
    on_add: Optional[Callable[[Player], None]] = None,
) -> None:
    """
    Render a table of players with add buttons.

    Args:
        players: List of players to display.
        team: Current team for validation context.
        on_add: Callback when player is added.
    """
    if not players:
        st.info("No players to display.")
        return

    for player in players:
        _render_player_row(player, team, on_add)


def _render_player_row(
    player: Player,
    team: Team,
    on_add: Optional[Callable[[Player], None]] = None,
) -> None:
    """Render a single player row."""
    cols = st.columns([3, 1, 1, 1])

    # Player info
    with cols[0]:
        st.markdown(f"**{player.name}**")
        st.caption(f"{player.country.value} · {player.position.value}")

    # Star value
    with cols[1]:
        st.markdown(f"⭐ **{player.star_value}**")

    # Ownership
    with cols[2]:
        if player.ownership_pct is not None:
            st.caption(f"{player.ownership_pct:.1f}%")

    # Add button
    with cols[3]:
        if on_add is not None:
            validation = can_add_player(team, player)
            button_disabled = not validation.is_valid

            help_text = None
            if not validation.is_valid and validation.errors:
                help_text = validation.errors[0].message

            if st.button(
                "➕",
                key=f"add_{player.id}",
                disabled=button_disabled,
                help=help_text,
            ):
                on_add(player)
                st.rerun()

    st.divider()
