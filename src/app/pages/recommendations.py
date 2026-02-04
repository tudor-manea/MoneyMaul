"""Recommendations page for captain picks, transfers, and analysis."""

import sys
from pathlib import Path

# Ensure project root is in path for direct page execution
_project_root = Path(__file__).parent.parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import streamlit as st

from src.models import Country, Player, Team
from src.analysis import (
    # Recommender
    PlayerRecommendation,
    TransferRecommendation,
    get_captain_recommendations,
    get_supersub_recommendations,
    get_transfer_suggestions,
    get_value_picks,
    get_differential_picks,
    # Form
    FormTrend,
    get_form_recommendations,
    get_improving_players,
    get_declining_players,
    # Fixtures
    DifficultyRating,
    TeamStrength,
    calculate_team_strengths,
    get_fixture_recommendations,
    get_favorable_captain_picks,
)
from src.scrapers import (
    ESPNScraper,
    FetchError,
    ParseError,
    RateLimitError,
    load_all_players_from_csv,
    generate_mock_player_points,
)


def _init_session_state() -> None:
    """Initialize session state variables."""
    if "team" not in st.session_state:
        st.session_state.team = Team()
    if "players" not in st.session_state:
        st.session_state.players = _get_players()
    if "player_points" not in st.session_state:
        st.session_state.player_points = _generate_points()
    if "matches" not in st.session_state:
        st.session_state.matches = _get_matches()
    if "match_stats" not in st.session_state:
        st.session_state.match_stats = _get_match_stats()


def _get_players() -> list[Player]:
    """
    Load all players from CSV prices file.

    This gives us all 228 players with proper prices and mock ownership.
    """
    players = load_all_players_from_csv()
    if players:
        st.session_state.data_source = "csv"
        return players

    # Fallback - shouldn't happen if CSV exists
    st.session_state.data_source = "error"
    return []


def _get_matches() -> list:
    """Get fixtures from ESPN API."""
    try:
        scraper = ESPNScraper()
        return scraper.scrape_fixtures(year=2026, use_cache=True)
    except (FetchError, ParseError, RateLimitError):
        return []


def _get_match_stats() -> list:
    """Get match stats from ESPN API for completed matches."""
    try:
        scraper = ESPNScraper()
        matches = st.session_state.get("matches", [])
        all_stats = []
        for match in matches:
            if match.is_completed:
                stats = scraper.scrape_match_stats(match.id, use_cache=True)
                all_stats.extend(stats)
        return all_stats
    except (FetchError, ParseError, RateLimitError):
        return []


def _generate_points() -> dict[str, float]:
    """Generate realistic varied mock points for all players."""
    players = st.session_state.get("players", [])
    return generate_mock_player_points(players, seed=42)  # Fixed seed for consistency


def _refresh_data() -> None:
    """Refresh all data."""
    st.session_state.players = _get_players()
    st.session_state.matches = _get_matches()
    st.session_state.match_stats = _get_match_stats()
    st.session_state.player_points = _generate_points()


def _get_historical_team_strengths() -> dict[Country, TeamStrength]:
    """
    Get historical team strengths based on recent Six Nations performance.

    Based on 2024 Six Nations results and World Rankings.
    """
    return {
        Country.IRELAND: TeamStrength(
            country=Country.IRELAND,
            matches_played=5,
            points_for=158,
            points_against=49,
            wins=5,
            point_differential=109,
            strength_score=100.0,  # Grand Slam 2024
        ),
        Country.FRANCE: TeamStrength(
            country=Country.FRANCE,
            matches_played=5,
            points_for=127,
            points_against=75,
            wins=3,
            point_differential=52,
            strength_score=75.0,
        ),
        Country.ENGLAND: TeamStrength(
            country=Country.ENGLAND,
            matches_played=5,
            points_for=92,
            points_against=82,
            wins=3,
            point_differential=10,
            strength_score=60.0,
        ),
        Country.SCOTLAND: TeamStrength(
            country=Country.SCOTLAND,
            matches_played=5,
            points_for=105,
            points_against=102,
            wins=2,
            point_differential=3,
            strength_score=50.0,
        ),
        Country.ITALY: TeamStrength(
            country=Country.ITALY,
            matches_played=5,
            points_for=83,
            points_against=119,
            wins=2,
            point_differential=-36,
            strength_score=35.0,
        ),
        Country.WALES: TeamStrength(
            country=Country.WALES,
            matches_played=5,
            points_for=56,
            points_against=194,
            wins=0,
            point_differential=-138,
            strength_score=10.0,  # Wooden Spoon 2024
        ),
    }


def _render_player_recommendation(rec: PlayerRecommendation, show_add: bool = False) -> None:
    """Render a single player recommendation."""
    cols = st.columns([3, 1, 2])

    with cols[0]:
        st.markdown(f"**{rec.player.name}**")
        st.caption(f"{rec.player.country.value} | {rec.player.position.value} | {rec.player.star_value}★")

    with cols[1]:
        st.metric("Score", f"{rec.score:.1f}")

    with cols[2]:
        st.caption(rec.reason)


def _render_transfer_recommendation(rec: TransferRecommendation) -> None:
    """Render a single transfer recommendation."""
    cols = st.columns([2, 1, 2, 1])

    with cols[0]:
        st.markdown(f"**OUT:** {rec.player_out.name}")
        st.caption(f"{rec.player_out.star_value}★")

    with cols[1]:
        st.markdown("→")

    with cols[2]:
        st.markdown(f"**IN:** {rec.player_in.name}")
        st.caption(f"{rec.player_in.star_value}★")

    with cols[3]:
        st.metric("Value Gain", f"+{rec.value_gain:.2f}")


def _render_form_recommendation(rec) -> None:
    """Render a form-based recommendation."""
    trend_icons = {
        FormTrend.IMPROVING: "📈",
        FormTrend.STABLE: "➡️",
        FormTrend.DECLINING: "📉",
    }

    cols = st.columns([3, 1, 2])

    with cols[0]:
        icon = trend_icons.get(rec.form.trend, "")
        st.markdown(f"**{rec.player.name}** {icon}")
        st.caption(f"{rec.player.country.value} | {rec.player.star_value}★")

    with cols[1]:
        st.metric("Avg Pts", f"{rec.form.average_points:.1f}")

    with cols[2]:
        st.caption(rec.reason)


def _render_fixture_recommendation(rec) -> None:
    """Render a fixture-based recommendation."""
    cols = st.columns([3, 1, 2])

    with cols[0]:
        st.markdown(f"**{rec.player.name}**")
        st.caption(f"{rec.player.country.value} | {rec.player.star_value}★")

    with cols[1]:
        difficulty = rec.upcoming_difficulty
        color = "green" if difficulty < 2.5 else "orange" if difficulty < 3.5 else "red"
        st.markdown(f":{color}[{difficulty:.1f}/5]")

    with cols[2]:
        st.caption(rec.reason)


def render() -> None:
    """Render the recommendations page."""
    _init_session_state()

    st.title("Recommendations")

    # Header with data status
    col1, col2 = st.columns([3, 1])
    with col1:
        team = st.session_state.team
        if team.players:
            st.success(f"Analyzing team with {len(team.players)} players")
        else:
            st.warning("No team selected. Build your team first for personalized recommendations.")
    with col2:
        st.button("Refresh Data", on_click=_refresh_data)

    st.divider()

    # Get data from session state
    team = st.session_state.team
    players = st.session_state.players
    player_points = st.session_state.player_points
    matches = st.session_state.matches
    match_stats = st.session_state.match_stats

    # Create tabs for different recommendation types
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "👑 Captain & Supersub",
        "🔄 Transfers",
        "💎 Value Picks",
        "📊 Form Analysis",
        "📅 Fixture Difficulty"
    ])

    # Tab 1: Captain & Supersub
    with tab1:
        if not team.players:
            st.info("Add players to your team to get captain/supersub recommendations.")
        else:
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("👑 Captain Picks")
                st.caption("Best players to captain (2x points)")

                captain_recs = get_captain_recommendations(team, player_points, top_n=5)
                if captain_recs:
                    for rec in captain_recs:
                        _render_player_recommendation(rec)
                        st.divider()
                else:
                    st.info("No captain recommendations available.")

            with col2:
                st.subheader("⚡ Supersub Picks")
                st.caption("Best impact subs (3x if subbed on, 0.5x otherwise)")

                supersub_recs = get_supersub_recommendations(team, player_points, top_n=5)
                if supersub_recs:
                    for rec in supersub_recs:
                        _render_player_recommendation(rec)
                        st.divider()
                else:
                    st.info("No supersub recommendations available.")

    # Tab 2: Transfers
    with tab2:
        if not team.players:
            st.info("Add players to your team to get transfer suggestions.")
        else:
            st.subheader("🔄 Transfer Suggestions")
            st.caption("Swaps that improve your team's points-per-star efficiency")

            transfer_recs = get_transfer_suggestions(team, players, player_points, top_n=10)
            if transfer_recs:
                for rec in transfer_recs:
                    _render_transfer_recommendation(rec)
                    st.divider()
            else:
                st.success("No value-improving transfers found. Your team is well optimized!")

    # Tab 3: Value Picks
    with tab3:
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("💎 Best Value Players")
            st.caption("Highest points per star ratio")

            value_recs = get_value_picks(players, player_points, team=team, top_n=10)
            if value_recs:
                for rec in value_recs:
                    _render_player_recommendation(rec)
                    st.divider()
            else:
                st.info("No value picks available.")

        with col2:
            st.subheader("🎯 Differential Picks")
            st.caption("Low ownership, high upside (< 10% owned)")

            diff_recs = get_differential_picks(players, player_points, max_ownership=10.0, team=team, top_n=10)
            if diff_recs:
                for rec in diff_recs:
                    _render_player_recommendation(rec)
                    st.divider()
            else:
                st.info("No differential picks with ownership data available.")

    # Tab 4: Form Analysis
    with tab4:
        if not matches or not match_stats:
            st.warning("Match data required for form analysis. Click 'Refresh Data' to load.")
        else:
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("📈 In-Form Players")
                st.caption("Players with improving recent performance")

                improving = get_improving_players(players, match_stats, matches, top_n=10)
                if improving:
                    for rec in improving:
                        _render_form_recommendation(rec)
                        st.divider()
                else:
                    st.info("No players with improving form found.")

            with col2:
                st.subheader("📉 Declining Form")
                st.caption("Consider transferring out")

                declining = get_declining_players(players, match_stats, matches, top_n=10)
                if declining:
                    for rec in declining:
                        _render_form_recommendation(rec)
                        st.divider()
                else:
                    st.info("No players with declining form found.")

    # Tab 5: Fixture Difficulty
    with tab5:
        if not matches:
            st.warning("Match data required for fixture analysis. Click 'Refresh Data' to load.")
        else:
            st.subheader("📅 Fixture Difficulty Analysis")

            # Determine which strengths to use
            computed_strengths = calculate_team_strengths(matches)
            # Check if any matches have been played (total across all teams)
            total_matches_played = sum(s.matches_played for s in computed_strengths.values())
            has_results = total_matches_played > 0

            if has_results:
                strengths = computed_strengths
                strength_source = "2026 Results"
            else:
                strengths = _get_historical_team_strengths()
                strength_source = "2024 Historical Data"

            # Show team strengths
            with st.expander(f"Team Strength Rankings ({strength_source})", expanded=False):
                sorted_strengths = sorted(strengths.values(), key=lambda s: s.strength_score, reverse=True)

                for i, strength in enumerate(sorted_strengths, 1):
                    cols = st.columns([1, 3, 1, 1, 1])
                    with cols[0]:
                        st.markdown(f"**{i}.**")
                    with cols[1]:
                        st.markdown(f"**{strength.country.value}**")
                    with cols[2]:
                        st.caption(f"W: {strength.wins}")
                    with cols[3]:
                        st.caption(f"PD: {strength.point_differential:+d}")
                    with cols[4]:
                        st.metric("", f"{strength.strength_score:.0f}")

            st.divider()

            col1, col2 = st.columns(2)

            with col1:
                st.subheader("🟢 Favorable Fixtures")
                st.caption("Players with easy upcoming matches")

                # Use historical strengths for recommendations if no results yet
                fixture_recs = get_fixture_recommendations(players, matches, gameweeks_ahead=2, top_n=10)
                if fixture_recs:
                    for rec in fixture_recs:
                        _render_fixture_recommendation(rec)
                        st.divider()
                else:
                    st.info("No fixture recommendations available.")

            with col2:
                st.subheader("👑 Fixture-Aware Captain Picks")
                st.caption("Best captain considering next fixture")

                captain_fixture_recs = get_favorable_captain_picks(players, player_points, matches, top_n=10)
                if captain_fixture_recs:
                    for rec in captain_fixture_recs:
                        _render_fixture_recommendation(rec)
                        st.divider()
                else:
                    st.info("No captain picks available.")


# Run the page when loaded by Streamlit
render()
