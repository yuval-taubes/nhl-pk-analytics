#!/usr/bin/env python3
"""Import local MoneyPuck CSVs into side-by-side mp_* tables."""

from __future__ import annotations

import argparse
import csv
import logging
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

from config import DB_CONFIG
from moneypuck.config import MONEYPUCK_FILES, MONEYPUCK_ROOT, validate_moneypuck_files


logger = logging.getLogger(__name__)
SCHEMA_PATH = Path(__file__).with_name("schema.sql")
BATCH_SIZE = 5000


SHOT_COLUMNS = [
    "season",
    "game_id",
    "shot_id",
    "home_team_code",
    "away_team_code",
    "is_playoff_game",
    "home_team_won",
    "period",
    "time_seconds",
    "event",
    "shooting_team_code",
    "defending_team_code",
    "is_home_shot",
    "home_goals",
    "away_goals",
    "home_skaters",
    "away_skaters",
    "shooting_skaters",
    "defending_skaters",
    "strength_state",
    "x_cord",
    "y_cord",
    "x_cord_adjusted",
    "y_cord_adjusted",
    "arena_adjusted_x_cord",
    "arena_adjusted_y_cord",
    "shot_angle",
    "shot_angle_adjusted",
    "shot_distance",
    "shot_type",
    "goal",
    "shot_was_on_goal",
    "shot_on_empty_net",
    "shot_rebound",
    "shot_generated_rebound",
    "shot_rush",
    "shot_goalie_froze",
    "shot_play_stopped",
    "shot_play_continued_in_zone",
    "shot_play_continued_outside_zone",
    "shot_angle_rebound_royal_road",
    "shot_angle_plus_rebound_speed",
    "off_wing",
    "x_goal",
    "x_froze",
    "x_rebound",
    "x_play_stopped",
    "x_play_continued_in_zone",
    "x_play_continued_outside_zone",
    "x_shot_was_on_goal",
    "time_since_last_event",
    "time_until_next_event",
    "time_since_faceoff",
    "time_difference_since_change",
    "shooter_player_id",
    "shooter_name",
    "shooter_left_right",
    "shooter_time_on_ice",
    "shooter_time_on_ice_since_faceoff",
    "goalie_id_for_shot",
    "goalie_name_for_shot",
    "shooting_team_average_time_on_ice",
    "shooting_team_max_time_on_ice",
    "defending_team_average_time_on_ice",
    "defending_team_max_time_on_ice",
    "defending_team_average_time_on_ice_since_faceoff",
    "defending_team_max_time_on_ice_since_faceoff",
    "home_penalty1_time_left",
    "home_penalty1_length",
    "away_penalty1_time_left",
    "away_penalty1_length",
    "last_event_category",
    "last_event_team",
    "last_event_x_cord",
    "last_event_y_cord",
    "last_event_x_cord_adjusted",
    "last_event_y_cord_adjusted",
    "distance_from_last_event",
    "speed_from_last_event",
]


TEAM_GAME_COLUMNS = [
    "season",
    "game_id",
    "game_date",
    "team",
    "opposing_team",
    "home_or_away",
    "situation",
    "playoff_game",
    "ice_time",
    "x_goals_for",
    "x_goals_against",
    "flurry_adjusted_x_goals_for",
    "flurry_adjusted_x_goals_against",
    "shot_attempts_for",
    "shot_attempts_against",
    "unblocked_shot_attempts_for",
    "unblocked_shot_attempts_against",
    "shots_on_goal_for",
    "shots_on_goal_against",
    "goals_for",
    "goals_against",
    "low_danger_x_goals_for",
    "medium_danger_x_goals_for",
    "high_danger_x_goals_for",
    "low_danger_x_goals_against",
    "medium_danger_x_goals_against",
    "high_danger_x_goals_against",
    "rebounds_for",
    "rebounds_against",
    "rebound_x_goals_for",
    "rebound_x_goals_against",
    "penalties_for",
    "penalties_against",
    "faceoffs_won_for",
    "faceoffs_won_against",
]


SKATER_COLUMNS = [
    "player_id",
    "season",
    "name",
    "team",
    "position",
    "situation",
    "games_played",
    "ice_time",
    "shifts",
    "game_score",
    "on_ice_x_goals_percentage",
    "off_ice_x_goals_percentage",
    "i_f_x_goals",
    "i_f_flurry_adjusted_x_goals",
    "i_f_shot_attempts",
    "i_f_shots_on_goal",
    "i_f_goals",
    "i_f_rebounds",
    "i_f_x_rebounds",
    "i_f_faceoffs_won",
    "faceoffs_won",
    "faceoffs_lost",
    "shots_blocked_by_player",
    "penalties",
    "penalties_drawn",
    "on_ice_f_x_goals",
    "on_ice_a_x_goals",
    "on_ice_f_shot_attempts",
    "on_ice_a_shot_attempts",
    "on_ice_a_high_danger_x_goals",
    "on_ice_a_medium_danger_x_goals",
    "on_ice_a_low_danger_x_goals",
    "off_ice_f_x_goals",
    "off_ice_a_x_goals",
    "x_goals_for_after_shifts",
    "x_goals_against_after_shifts",
]


GOALIE_COLUMNS = [
    "player_id",
    "season",
    "name",
    "team",
    "position",
    "situation",
    "games_played",
    "ice_time",
    "x_goals",
    "goals",
    "unblocked_shot_attempts",
    "x_rebounds",
    "rebounds",
    "x_freeze",
    "freezes",
    "x_on_goal",
    "on_goal",
    "flurry_adjusted_x_goals",
    "low_danger_x_goals",
    "medium_danger_x_goals",
    "high_danger_x_goals",
    "low_danger_goals",
    "medium_danger_goals",
    "high_danger_goals",
]


TEAM_SEASON_COLUMNS = [
    "team",
    "season",
    "situation",
    "games_played",
    "ice_time",
    "x_goals_for",
    "x_goals_against",
    "flurry_adjusted_x_goals_for",
    "flurry_adjusted_x_goals_against",
    "shot_attempts_for",
    "shot_attempts_against",
    "goals_for",
    "goals_against",
    "high_danger_x_goals_for",
    "high_danger_x_goals_against",
    "rebound_x_goals_for",
    "rebound_x_goals_against",
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="Truncate mp_* tables before import.")
    parser.add_argument("--skip-shots", action="store_true", help="Skip the large shot file.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    missing = validate_moneypuck_files()
    if missing:
        raise FileNotFoundError(f"Missing MoneyPuck files: {missing}")

    with psycopg2.connect(**DB_CONFIG) as conn:
        initialize_schema(conn)
        if args.reset:
            reset_tables(conn)

        counts = {
            "shots_rows": 0 if args.skip_shots else import_csv(conn, "mp_shots", SHOT_COLUMNS, MONEYPUCK_FILES["shots"], map_shot_row),
            "team_game_rows": import_csv(conn, "mp_team_games", TEAM_GAME_COLUMNS, MONEYPUCK_FILES["team_games"], map_team_game_row),
            "skater_rows": import_csv(conn, "mp_skaters_season", SKATER_COLUMNS, MONEYPUCK_FILES["skaters"], map_skater_row),
            "goalie_rows": import_csv(conn, "mp_goalies_season", GOALIE_COLUMNS, MONEYPUCK_FILES["goalies"], map_goalie_row),
            "team_season_rows": import_csv(conn, "mp_teams_season", TEAM_SEASON_COLUMNS, MONEYPUCK_FILES["teams"], map_team_season_row),
        }
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO mp_import_runs
                    (source_root, shots_rows, team_game_rows, skater_rows, goalie_rows, team_season_rows)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    str(MONEYPUCK_ROOT),
                    counts["shots_rows"],
                    counts["team_game_rows"],
                    counts["skater_rows"],
                    counts["goalie_rows"],
                    counts["team_season_rows"],
                ),
            )
        logger.info("MoneyPuck import complete: %s", counts)


def initialize_schema(conn):
    with conn.cursor() as cur:
        cur.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()


def reset_tables(conn):
    logger.warning("Truncating MoneyPuck v2 tables...")
    with conn.cursor() as cur:
        cur.execute(
            """
            TRUNCATE
                mp_import_runs,
                mp_shots,
                mp_team_games,
                mp_skaters_season,
                mp_goalies_season,
                mp_teams_season
            RESTART IDENTITY
            """
        )
    conn.commit()


def import_csv(conn, table, columns, path, mapper):
    sql = f"""
        INSERT INTO {table} ({", ".join(columns)})
        VALUES %s
        ON CONFLICT DO NOTHING
        RETURNING 1
    """
    total = 0
    batch = []
    logger.info("Importing %s from %s", table, path)
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for source_row in reader:
            mapped = mapper(source_row)
            if mapped is None:
                continue
            batch.append(tuple(mapped[col] for col in columns))
            if len(batch) >= BATCH_SIZE:
                total += flush(conn, sql, batch)
                batch.clear()
                if total % 100000 == 0:
                    logger.info("%s rows processed for %s", total, table)
        if batch:
            total += flush(conn, sql, batch)
    logger.info("Imported %s rows into %s", total, table)
    return total


def flush(conn, sql, batch):
    with conn.cursor() as cur:
        inserted = execute_values(cur, sql, batch, page_size=BATCH_SIZE, fetch=True)
    conn.commit()
    return len(inserted)


def map_shot_row(row):
    home_skaters = to_int(row.get("homeSkatersOnIce"))
    away_skaters = to_int(row.get("awaySkatersOnIce"))
    is_home = to_bool(row.get("isHomeTeam"))
    shooting_skaters = home_skaters if is_home else away_skaters
    defending_skaters = away_skaters if is_home else home_skaters
    home_team = clean(row.get("homeTeamCode"))
    away_team = clean(row.get("awayTeamCode"))
    shooting_team = clean(row.get("teamCode")) or (home_team if is_home else away_team)
    defending_team = away_team if is_home else home_team

    return {
        "season": to_int(row.get("season")),
        "game_id": to_int(row.get("game_id")),
        "shot_id": to_int(row.get("shotID")),
        "home_team_code": home_team,
        "away_team_code": away_team,
        "is_playoff_game": to_bool(row.get("isPlayoffGame")),
        "home_team_won": to_bool(row.get("homeTeamWon")),
        "period": to_int(row.get("period")),
        "time_seconds": to_int(row.get("time")),
        "event": clean(row.get("event")),
        "shooting_team_code": shooting_team,
        "defending_team_code": defending_team,
        "is_home_shot": is_home,
        "home_goals": to_int(row.get("homeTeamGoals")),
        "away_goals": to_int(row.get("awayTeamGoals")),
        "home_skaters": home_skaters,
        "away_skaters": away_skaters,
        "shooting_skaters": shooting_skaters,
        "defending_skaters": defending_skaters,
        "strength_state": f"{shooting_skaters}on{defending_skaters}" if shooting_skaters and defending_skaters else None,
        "x_cord": to_float(row.get("xCord")),
        "y_cord": to_float(row.get("yCord")),
        "x_cord_adjusted": to_float(row.get("xCordAdjusted")),
        "y_cord_adjusted": to_float(row.get("yCordAdjusted")),
        "arena_adjusted_x_cord": to_float(row.get("arenaAdjustedXCord")),
        "arena_adjusted_y_cord": to_float(row.get("arenaAdjustedYCord")),
        "shot_angle": to_float(row.get("shotAngle")),
        "shot_angle_adjusted": to_float(row.get("shotAngleAdjusted")),
        "shot_distance": to_float(row.get("shotDistance")),
        "shot_type": clean(row.get("shotType")),
        "goal": to_bool(row.get("goal")),
        "shot_was_on_goal": to_bool(row.get("shotWasOnGoal")),
        "shot_on_empty_net": to_bool(row.get("shotOnEmptyNet")),
        "shot_rebound": to_bool(row.get("shotRebound")),
        "shot_generated_rebound": to_bool(row.get("shotGeneratedRebound")),
        "shot_rush": to_bool(row.get("shotRush")),
        "shot_goalie_froze": to_bool(row.get("shotGoalieFroze")),
        "shot_play_stopped": to_bool(row.get("shotPlayStopped")),
        "shot_play_continued_in_zone": to_bool(row.get("shotPlayContinuedInZone")),
        "shot_play_continued_outside_zone": to_bool(row.get("shotPlayContinuedOutsideZone")),
        "shot_angle_rebound_royal_road": to_bool(row.get("shotAngleReboundRoyalRoad")),
        "shot_angle_plus_rebound_speed": to_float(row.get("shotAnglePlusReboundSpeed")),
        "off_wing": to_bool(row.get("offWing")),
        "x_goal": to_float(row.get("xGoal")),
        "x_froze": to_float(row.get("xFroze")),
        "x_rebound": to_float(row.get("xRebound")),
        "x_play_stopped": to_float(row.get("xPlayStopped")),
        "x_play_continued_in_zone": to_float(row.get("xPlayContinuedInZone")),
        "x_play_continued_outside_zone": to_float(row.get("xPlayContinuedOutsideZone")),
        "x_shot_was_on_goal": to_float(row.get("xShotWasOnGoal")),
        "time_since_last_event": to_float(row.get("timeSinceLastEvent")),
        "time_until_next_event": to_float(row.get("timeUntilNextEvent")),
        "time_since_faceoff": to_float(row.get("timeSinceFaceoff")),
        "time_difference_since_change": to_float(row.get("timeDifferenceSinceChange")),
        "shooter_player_id": to_int(row.get("shooterPlayerId")),
        "shooter_name": clean(row.get("shooterName")),
        "shooter_left_right": clean(row.get("shooterLeftRight")),
        "shooter_time_on_ice": to_float(row.get("shooterTimeOnIce")),
        "shooter_time_on_ice_since_faceoff": to_float(row.get("shooterTimeOnIceSinceFaceoff")),
        "goalie_id_for_shot": to_int(row.get("goalieIdForShot")),
        "goalie_name_for_shot": clean(row.get("goalieNameForShot")),
        "shooting_team_average_time_on_ice": to_float(row.get("shootingTeamAverageTimeOnIce")),
        "shooting_team_max_time_on_ice": to_float(row.get("shootingTeamMaxTimeOnIce")),
        "defending_team_average_time_on_ice": to_float(row.get("defendingTeamAverageTimeOnIce")),
        "defending_team_max_time_on_ice": to_float(row.get("defendingTeamMaxTimeOnIce")),
        "defending_team_average_time_on_ice_since_faceoff": to_float(row.get("defendingTeamAverageTimeOnIceSinceFaceoff")),
        "defending_team_max_time_on_ice_since_faceoff": to_float(row.get("defendingTeamMaxTimeOnIceSinceFaceoff")),
        "home_penalty1_time_left": to_float(row.get("homePenalty1TimeLeft")),
        "home_penalty1_length": to_float(row.get("homePenalty1Length")),
        "away_penalty1_time_left": to_float(row.get("awayPenalty1TimeLeft")),
        "away_penalty1_length": to_float(row.get("awayPenalty1Length")),
        "last_event_category": clean(row.get("lastEventCategory")),
        "last_event_team": clean(row.get("lastEventTeam")),
        "last_event_x_cord": to_float(row.get("lastEventxCord")),
        "last_event_y_cord": to_float(row.get("lastEventyCord")),
        "last_event_x_cord_adjusted": to_float(row.get("lastEventxCord_adjusted")),
        "last_event_y_cord_adjusted": to_float(row.get("lastEventyCord_adjusted")),
        "distance_from_last_event": to_float(row.get("distanceFromLastEvent")),
        "speed_from_last_event": to_float(row.get("speedFromLastEvent")),
    }


def map_team_game_row(row):
    return {
        "season": to_int(row.get("season")),
        "game_id": to_int(row.get("gameId")),
        "game_date": to_date(row.get("gameDate")),
        "team": clean(row.get("team")),
        "opposing_team": clean(row.get("opposingTeam")),
        "home_or_away": clean(row.get("home_or_away")),
        "situation": clean(row.get("situation")),
        "playoff_game": to_bool(row.get("playoffGame")),
        "ice_time": to_float(row.get("iceTime")),
        "x_goals_for": to_float(row.get("xGoalsFor")),
        "x_goals_against": to_float(row.get("xGoalsAgainst")),
        "flurry_adjusted_x_goals_for": to_float(row.get("flurryAdjustedxGoalsFor")),
        "flurry_adjusted_x_goals_against": to_float(row.get("flurryAdjustedxGoalsAgainst")),
        "shot_attempts_for": to_float(row.get("shotAttemptsFor")),
        "shot_attempts_against": to_float(row.get("shotAttemptsAgainst")),
        "unblocked_shot_attempts_for": to_float(row.get("unblockedShotAttemptsFor")),
        "unblocked_shot_attempts_against": to_float(row.get("unblockedShotAttemptsAgainst")),
        "shots_on_goal_for": to_float(row.get("shotsOnGoalFor")),
        "shots_on_goal_against": to_float(row.get("shotsOnGoalAgainst")),
        "goals_for": to_float(row.get("goalsFor")),
        "goals_against": to_float(row.get("goalsAgainst")),
        "low_danger_x_goals_for": to_float(row.get("lowDangerxGoalsFor")),
        "medium_danger_x_goals_for": to_float(row.get("mediumDangerxGoalsFor")),
        "high_danger_x_goals_for": to_float(row.get("highDangerxGoalsFor")),
        "low_danger_x_goals_against": to_float(row.get("lowDangerxGoalsAgainst")),
        "medium_danger_x_goals_against": to_float(row.get("mediumDangerxGoalsAgainst")),
        "high_danger_x_goals_against": to_float(row.get("highDangerxGoalsAgainst")),
        "rebounds_for": to_float(row.get("reboundsFor")),
        "rebounds_against": to_float(row.get("reboundsAgainst")),
        "rebound_x_goals_for": to_float(row.get("reboundxGoalsFor")),
        "rebound_x_goals_against": to_float(row.get("reboundxGoalsAgainst")),
        "penalties_for": to_float(row.get("penaltiesFor")),
        "penalties_against": to_float(row.get("penaltiesAgainst")),
        "faceoffs_won_for": to_float(row.get("faceOffsWonFor")),
        "faceoffs_won_against": to_float(row.get("faceOffsWonAgainst")),
    }


def map_skater_row(row):
    return {
        "player_id": to_int(row.get("playerId")),
        "season": to_int(row.get("season")),
        "name": clean(row.get("name")),
        "team": clean(row.get("team")),
        "position": clean(row.get("position")),
        "situation": clean(row.get("situation")),
        "games_played": to_float(row.get("games_played")),
        "ice_time": to_float(row.get("icetime")),
        "shifts": to_float(row.get("shifts")),
        "game_score": to_float(row.get("gameScore")),
        "on_ice_x_goals_percentage": to_float(row.get("onIce_xGoalsPercentage")),
        "off_ice_x_goals_percentage": to_float(row.get("offIce_xGoalsPercentage")),
        "i_f_x_goals": to_float(row.get("I_F_xGoals")),
        "i_f_flurry_adjusted_x_goals": to_float(row.get("I_F_flurryAdjustedxGoals")),
        "i_f_shot_attempts": to_float(row.get("I_F_shotAttempts")),
        "i_f_shots_on_goal": to_float(row.get("I_F_shotsOnGoal")),
        "i_f_goals": to_float(row.get("I_F_goals")),
        "i_f_rebounds": to_float(row.get("I_F_rebounds")),
        "i_f_x_rebounds": to_float(row.get("I_F_xRebounds")),
        "i_f_faceoffs_won": to_float(row.get("I_F_faceOffsWon")),
        "faceoffs_won": to_float(row.get("faceoffsWon")),
        "faceoffs_lost": to_float(row.get("faceoffsLost")),
        "shots_blocked_by_player": to_float(row.get("shotsBlockedByPlayer")),
        "penalties": to_float(row.get("penalties")),
        "penalties_drawn": to_float(row.get("penaltiesDrawn")),
        "on_ice_f_x_goals": to_float(row.get("OnIce_F_xGoals")),
        "on_ice_a_x_goals": to_float(row.get("OnIce_A_xGoals")),
        "on_ice_f_shot_attempts": to_float(row.get("OnIce_F_shotAttempts")),
        "on_ice_a_shot_attempts": to_float(row.get("OnIce_A_shotAttempts")),
        "on_ice_a_high_danger_x_goals": to_float(row.get("OnIce_A_highDangerxGoals")),
        "on_ice_a_medium_danger_x_goals": to_float(row.get("OnIce_A_mediumDangerxGoals")),
        "on_ice_a_low_danger_x_goals": to_float(row.get("OnIce_A_lowDangerxGoals")),
        "off_ice_f_x_goals": to_float(row.get("OffIce_F_xGoals")),
        "off_ice_a_x_goals": to_float(row.get("OffIce_A_xGoals")),
        "x_goals_for_after_shifts": to_float(row.get("xGoalsForAfterShifts")),
        "x_goals_against_after_shifts": to_float(row.get("xGoalsAgainstAfterShifts")),
    }


def map_goalie_row(row):
    return {
        "player_id": to_int(row.get("playerId")),
        "season": to_int(row.get("season")),
        "name": clean(row.get("name")),
        "team": clean(row.get("team")),
        "position": clean(row.get("position")),
        "situation": clean(row.get("situation")),
        "games_played": to_float(row.get("games_played")),
        "ice_time": to_float(row.get("icetime")),
        "x_goals": to_float(row.get("xGoals")),
        "goals": to_float(row.get("goals")),
        "unblocked_shot_attempts": to_float(row.get("unblocked_shot_attempts")),
        "x_rebounds": to_float(row.get("xRebounds")),
        "rebounds": to_float(row.get("rebounds")),
        "x_freeze": to_float(row.get("xFreeze")),
        "freezes": to_float(row.get("freeze")),
        "x_on_goal": to_float(row.get("xOnGoal")),
        "on_goal": to_float(row.get("ongoal")),
        "flurry_adjusted_x_goals": to_float(row.get("flurryAdjustedxGoals")),
        "low_danger_x_goals": to_float(row.get("lowDangerxGoals")),
        "medium_danger_x_goals": to_float(row.get("mediumDangerxGoals")),
        "high_danger_x_goals": to_float(row.get("highDangerxGoals")),
        "low_danger_goals": to_float(row.get("lowDangerGoals")),
        "medium_danger_goals": to_float(row.get("mediumDangerGoals")),
        "high_danger_goals": to_float(row.get("highDangerGoals")),
    }


def map_team_season_row(row):
    return {
        "team": clean(row.get("team")),
        "season": to_int(row.get("season")),
        "situation": clean(row.get("situation")),
        "games_played": to_float(row.get("games_played")),
        "ice_time": to_float(row.get("iceTime")),
        "x_goals_for": to_float(row.get("xGoalsFor")),
        "x_goals_against": to_float(row.get("xGoalsAgainst")),
        "flurry_adjusted_x_goals_for": to_float(row.get("flurryAdjustedxGoalsFor")),
        "flurry_adjusted_x_goals_against": to_float(row.get("flurryAdjustedxGoalsAgainst")),
        "shot_attempts_for": to_float(row.get("shotAttemptsFor")),
        "shot_attempts_against": to_float(row.get("shotAttemptsAgainst")),
        "goals_for": to_float(row.get("goalsFor")),
        "goals_against": to_float(row.get("goalsAgainst")),
        "high_danger_x_goals_for": to_float(row.get("highDangerxGoalsFor")),
        "high_danger_x_goals_against": to_float(row.get("highDangerxGoalsAgainst")),
        "rebound_x_goals_for": to_float(row.get("reboundxGoalsFor")),
        "rebound_x_goals_against": to_float(row.get("reboundxGoalsAgainst")),
    }


def clean(value):
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def to_float(value):
    text = clean(value)
    if text is None:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def to_int(value):
    number = to_float(value)
    return int(number) if number is not None else None


def to_bool(value):
    number = to_float(value)
    if number is not None:
        return number == 1
    text = clean(value)
    return text.lower() in {"true", "t", "yes"} if text else None


def to_date(value):
    text = clean(value)
    if not text:
        return None
    if len(text) == 8 and text.isdigit():
        return f"{text[0:4]}-{text[4:6]}-{text[6:8]}"
    return text


if __name__ == "__main__":
    main()
