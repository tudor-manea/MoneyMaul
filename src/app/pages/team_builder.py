"""Team builder page for selecting and managing fantasy team."""

import sys
from pathlib import Path

# Ensure project root is in path for direct page execution
_project_root = Path(__file__).parent.parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import streamlit as st

from src.models import Country, Player, Position, Team, MAX_BUDGET, MAX_PER_COUNTRY
from src.analysis import (
    auto_select_team,
    can_add_player,
    validate_team,
    get_available_slots_for_country,
    get_squad_slots_remaining,
)
from src.scrapers import (
    ESPNScraper,
    FetchError,
    ParseError,
    RateLimitError,
    apply_prices_to_players,
    create_sample_players,
    generate_mock_player_points,
    calculate_form_based_points,
    load_all_players_from_csv,
    load_static_lineups,
)
from src.app.components import render_player_table, render_team_status, render_validation


def _init_session_state() -> None:
    """Initialize session state variables."""
    if "team" not in st.session_state:
        st.session_state.team = Team()
    if "players" not in st.session_state:
        st.session_state.players = _get_players()
    if "data_source" not in st.session_state:
        st.session_state.data_source = "unknown"


def _get_players() -> list[Player]:
    """
    Get players from CSV prices file (all 228 players).

    Falls back to ESPN API or sample data if CSV is not available.

    Returns:
        List of Player objects.
    """
    # Primary: Load all players from CSV (most complete data)
    csv_players = load_all_players_from_csv()
    if csv_players:
        st.session_state.data_source = "csv"
        return csv_players

    # Fallback: ESPN API
    try:
        return _fetch_espn_players()
    except (FetchError, ParseError, RateLimitError, ValueError):
        # Last resort: sample data
        st.session_state.data_source = "sample"
        return _get_sample_players()


def _fetch_espn_players() -> list[Player]:
    """
    Fetch real players from ESPN API and apply prices from CSV.

    Returns:
        List of Player objects with prices from CSV (or defaults).
    """
    scraper = ESPNScraper()
    espn_players = scraper.scrape_all_players(year=2026, use_cache=True)

    if not espn_players:
        raise ValueError("No players found from ESPN API")

    # Apply prices from CSV file (falls back to defaults if not found)
    players_with_prices = apply_prices_to_players(espn_players)

    st.session_state.data_source = "espn"
    return players_with_prices


def _get_sample_players() -> list[Player]:
    """Get sample player list for testing/fallback."""
    base_players = create_sample_players()

    # Add more players to enable full team building
    additional_players = [
        # More England
        Player(
            id="ollie-lawrence",
            name="Ollie Lawrence",
            country=Country.ENGLAND,
            position=Position.BACK,
            star_value=12.0,
            ownership_pct=22.3,
        ),
        Player(
            id="ben-earl",
            name="Ben Earl",
            country=Country.ENGLAND,
            position=Position.FORWARD,
            star_value=12.5,
            ownership_pct=31.2,
        ),
        # More France
        Player(
            id="damian-penaud",
            name="Damian Penaud",
            country=Country.FRANCE,
            position=Position.BACK,
            star_value=14.5,
            ownership_pct=48.7,
        ),
        Player(
            id="charles-ollivon",
            name="Charles Ollivon",
            country=Country.FRANCE,
            position=Position.FORWARD,
            star_value=13.0,
            ownership_pct=33.9,
        ),
        # More Ireland
        Player(
            id="james-lowe",
            name="James Lowe",
            country=Country.IRELAND,
            position=Position.BACK,
            star_value=13.0,
            ownership_pct=42.1,
        ),
        Player(
            id="caelan-doris",
            name="Caelan Doris",
            country=Country.IRELAND,
            position=Position.FORWARD,
            star_value=14.0,
            ownership_pct=47.3,
        ),
        # More Italy
        Player(
            id="tommaso-allan",
            name="Tommaso Allan",
            country=Country.ITALY,
            position=Position.BACK,
            star_value=9.5,
            ownership_pct=8.2,
        ),
        Player(
            id="sebastian-negri",
            name="Sebastian Negri",
            country=Country.ITALY,
            position=Position.FORWARD,
            star_value=10.0,
            ownership_pct=12.4,
        ),
        # More Scotland
        Player(
            id="duhan-van-der-merwe",
            name="Duhan van der Merwe",
            country=Country.SCOTLAND,
            position=Position.BACK,
            star_value=13.5,
            ownership_pct=51.8,
        ),
        Player(
            id="jamie-ritchie",
            name="Jamie Ritchie",
            country=Country.SCOTLAND,
            position=Position.FORWARD,
            star_value=11.5,
            ownership_pct=24.6,
        ),
        # More Wales
        Player(
            id="liam-williams",
            name="Liam Williams",
            country=Country.WALES,
            position=Position.BACK,
            star_value=11.0,
            ownership_pct=19.5,
        ),
        Player(
            id="taulupe-faletau",
            name="Taulupe Faletau",
            country=Country.WALES,
            position=Position.FORWARD,
            star_value=12.0,
            ownership_pct=27.3,
        ),
        # Budget options
        Player(
            id="george-ford",
            name="George Ford",
            country=Country.ENGLAND,
            position=Position.BACK,
            star_value=11.0,
            ownership_pct=15.8,
        ),
        Player(
            id="thomas-ramos",
            name="Thomas Ramos",
            country=Country.FRANCE,
            position=Position.BACK,
            star_value=13.5,
            ownership_pct=38.4,
        ),
        Player(
            id="hugo-keenan",
            name="Hugo Keenan",
            country=Country.IRELAND,
            position=Position.BACK,
            star_value=12.5,
            ownership_pct=35.6,
        ),
        Player(
            id="paolo-garbisi",
            name="Paolo Garbisi",
            country=Country.ITALY,
            position=Position.BACK,
            star_value=10.5,
            ownership_pct=14.1,
        ),
        Player(
            id="blair-kinghorn",
            name="Blair Kinghorn",
            country=Country.SCOTLAND,
            position=Position.BACK,
            star_value=11.5,
            ownership_pct=20.3,
        ),
        Player(
            id="tomos-williams",
            name="Tomos Williams",
            country=Country.WALES,
            position=Position.BACK,
            star_value=10.5,
            ownership_pct=16.7,
        ),
    ]

    return base_players + additional_players


def _get_team_player_ids() -> set[str]:
    """Get set of player IDs currently in team."""
    return {p.id for p in st.session_state.team.players}


def _add_player(player: Player) -> None:
    """Add player to team if valid."""
    result = can_add_player(st.session_state.team, player)
    if result.is_valid:
        st.session_state.team.add_player(player)
    else:
        error_msg = result.errors[0].message if result.errors else "Unknown error"
        st.error(f"Cannot add {player.name}: {error_msg}")


def _remove_player(player_id: str) -> None:
    """Remove player from team."""
    st.session_state.team.remove_player(player_id)


def _set_captain(player_id: str) -> None:
    """Set player as captain."""
    st.session_state.team.set_captain(player_id)


def _set_supersub(player_id: str) -> None:
    """Set player as supersub."""
    st.session_state.team.set_supersub(player_id)


def _clear_captain() -> None:
    """Clear captain selection."""
    st.session_state.team.captain_id = None


def _clear_supersub() -> None:
    """Clear supersub selection."""
    st.session_state.team.supersub_id = None


def _refresh_players() -> None:
    """Refresh player data from ESPN API."""
    st.session_state.players = _get_players()


def _auto_select_team() -> None:
    """Auto-select optimal team using real form data."""
    players = st.session_state.players

    # Use real form-based points, fall back to mock if unavailable
    try:
        player_points = calculate_form_based_points(players, form_year=2025, lineup_year=2026)
    except Exception:
        player_points = generate_mock_player_points(players, seed=42)

    # Select optimal team (captain is set by auto_select_team)
    team = auto_select_team(players, player_points)

    # Set supersub as best bench player (not a starter)
    lineup_status = load_static_lineups()
    bench_players = []
    for player in team.players:
        if player.id == team.captain_id:
            continue
        # Check if player is a bench player (not a starter)
        name_parts = player.name.split()
        surname = name_parts[-1] if name_parts else player.name
        is_starter = False
        for lineup_name, starter_status in lineup_status.items():
            if surname.lower() in lineup_name.lower() and starter_status:
                is_starter = True
                break
        if not is_starter:
            bench_players.append(player)

    if bench_players:
        # Pick bench player with highest expected points
        best_bench = max(bench_players, key=lambda p: player_points.get(p.id, 0.0))
        team.supersub_id = best_bench.id
    elif team.players:
        # Fallback: pick second highest points player if no bench players identified
        remaining = [p for p in team.players if p.id != team.captain_id]
        if remaining:
            best_supersub = max(remaining, key=lambda p: player_points.get(p.id, 0.0))
            team.supersub_id = best_supersub.id

    st.session_state.team = team


def render() -> None:
    """Render the team builder page."""
    _init_session_state()

    st.title("Team Builder")

    # Data source indicator
    source = st.session_state.get("data_source", "unknown")
    col1, col2 = st.columns([3, 1])
    with col1:
        if source == "csv":
            st.success(f"Using player database ({len(st.session_state.players)} players)")
        elif source == "espn":
            st.success(f"Using ESPN data ({len(st.session_state.players)} players)")
        elif source == "sample":
            st.warning("Using sample data (data unavailable)")
        else:
            st.info("Loading player data...")
    with col2:
        st.button("Refresh Data", on_click=_refresh_players, key="team_builder_refresh")

    st.divider()

    # Layout: Two columns - team on left, available players on right
    team_col, players_col = st.columns([1, 1.5])

    with team_col:
        st.header("Your Team")
        render_team_status(st.session_state.team)

        # Auto-select button
        st.button(
            "Auto-Select Best Team",
            on_click=_auto_select_team,
            key="auto_select_btn",
            type="primary",
            help="Automatically pick the optimal 15 players within budget and country constraints"
        )

        st.subheader("Squad")
        if st.session_state.team.players:
            for player in st.session_state.team.players:
                _render_team_player_row(player)
        else:
            st.info("No players selected. Add players from the list on the right.")

        # Validation status
        st.divider()
        result = validate_team(st.session_state.team)
        render_validation(result)

    with players_col:
        st.header("Available Players")

        # Filters
        filter_col1, filter_col2, filter_col3 = st.columns(3)

        with filter_col1:
            country_filter = st.selectbox(
                "Country",
                ["All"] + [c.value for c in Country],
                key="country_filter",
            )

        with filter_col2:
            position_filter = st.selectbox(
                "Position",
                ["All", "Forward", "Back"],
                key="position_filter",
            )

        with filter_col3:
            max_price = st.slider(
                "Max Price",
                min_value=8.0,
                max_value=20.0,
                value=max(8.0, min(float(st.session_state.team.budget_remaining), 20.0)),
                step=0.5,
                key="max_price_filter",
            )

        # Filter players
        filtered_players = _filter_players(
            st.session_state.players,
            country_filter,
            position_filter,
            max_price,
        )

        # Show available players
        team_player_ids = _get_team_player_ids()
        available_players = [p for p in filtered_players if p.id not in team_player_ids]

        if available_players:
            render_player_table(
                available_players,
                st.session_state.team,
                on_add=_add_player,
            )
        else:
            st.info("No players match your filters.")


def _render_team_player_row(player: Player) -> None:
    """Render a player row in the team section."""
    team = st.session_state.team

    cols = st.columns([3, 1, 1, 1])

    # Player info
    with cols[0]:
        role_badge = ""
        if team.captain_id == player.id:
            role_badge = " 👑"
        elif team.supersub_id == player.id:
            role_badge = " ⚡"

        st.markdown(f"**{player.name}**{role_badge}")
        st.caption(f"{player.country.value} · {player.position.value} · ⭐ {player.star_value}")

    # Captain button
    with cols[1]:
        if team.captain_id == player.id:
            st.button("✓ C", key=f"clear_c_{player.id}", on_click=_clear_captain, help="Remove captain")
        elif team.supersub_id != player.id:
            st.button("C", key=f"set_c_{player.id}", on_click=_set_captain, args=(player.id,), help="Set as captain")

    # Supersub button
    with cols[2]:
        if team.supersub_id == player.id:
            st.button("✓ S", key=f"clear_s_{player.id}", on_click=_clear_supersub, help="Remove supersub")
        elif team.captain_id != player.id:
            st.button("S", key=f"set_s_{player.id}", on_click=_set_supersub, args=(player.id,), help="Set as supersub")

    # Remove button
    with cols[3]:
        st.button("🗑️", key=f"remove_{player.id}", on_click=_remove_player, args=(player.id,), help="Remove player")

    st.divider()


def _filter_players(
    players: list[Player],
    country: str,
    position: str,
    max_price: float,
) -> list[Player]:
    """Filter players by criteria."""
    filtered = players

    if country != "All":
        filtered = [p for p in filtered if p.country.value == country]

    if position != "All":
        position_enum = Position.FORWARD if position == "Forward" else Position.BACK
        filtered = [p for p in filtered if p.position == position_enum]

    filtered = [p for p in filtered if p.star_value <= max_price]

    # Sort by star value (descending)
    return sorted(filtered, key=lambda p: p.star_value, reverse=True)


# Run the page when loaded by Streamlit
render()
