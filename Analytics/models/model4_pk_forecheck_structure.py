"""Model 4: Aggressive vs passive PK forecheck structure."""

import logging

from db import DatabaseConnection
from models.model_utils import add_timestamp, bootstrap_ci_by_game, export_json

logger = logging.getLogger(__name__)


class PkForecheckStructureModel:
    """Descriptive comparison of forecheck-structure proxies on PP entries."""

    def __init__(self, db_connection):
        self.db = db_connection
        self.data = None

    def fetch_data(self):
        query = """
        WITH pp_entries AS (
            SELECT
                p.possession_id,
                p.game_id,
                p.team_id AS pp_team_id,
                p.entry_type,
                p.strength,
                p.duration_seconds,
                p.xg_sum,
                se.event_id AS start_event_id,
                se.event_idx AS start_idx,
                se.period,
                se.period_time_seconds,
                g.home_team_id,
                g.away_team_id,
                CASE
                    WHEN split_part(p.strength, 'v', 1)::int < split_part(p.strength, 'v', 2)::int THEN g.away_team_id
                    WHEN split_part(p.strength, 'v', 2)::int < split_part(p.strength, 'v', 1)::int THEN g.home_team_id
                END AS pk_team_id
            FROM possessions p
            JOIN games g ON p.game_id = g.game_id
            JOIN events se ON p.start_event_id = se.event_id
            WHERE p.strength IN ('4v5', '3v5', '3v4', '5v4', '5v3', '4v3')
              AND p.entry_type IN ('CONTROLLED', 'DUMP_IN')
              AND p.team_id = CASE
                    WHEN split_part(p.strength, 'v', 1)::int > split_part(p.strength, 'v', 2)::int THEN g.away_team_id
                    WHEN split_part(p.strength, 'v', 2)::int > split_part(p.strength, 'v', 1)::int THEN g.home_team_id
              END
        ),
        pressure_proxy AS (
            SELECT
                e.possession_id,
                COUNT(DISTINCT ep.player_id) AS linked_pk_forecheckers
            FROM pp_entries e
            JOIN events prior
              ON prior.game_id = e.game_id
             AND prior.event_idx BETWEEN GREATEST(e.start_idx - 3, 0) AND e.start_idx
             AND prior.event_team_id = e.pk_team_id
             AND prior.x_norm > 50
            JOIN event_players ep
              ON ep.event_id = prior.event_id
             AND ep.team_id = e.pk_team_id
            GROUP BY e.possession_id
        ),
        shots_30 AS (
            SELECT
                e.possession_id,
                COALESCE(SUM(s.xg), 0) AS xga_30,
                COUNT(s.shot_id) AS shots_30,
                SUM(CASE WHEN se.description ILIKE '%rush%' OR se.description ILIKE '%2-on-1%' OR se.description ILIKE '%3-on-2%' THEN 1 ELSE 0 END) AS rush_shots
            FROM pp_entries e
            LEFT JOIN events se
              ON se.game_id = e.game_id
             AND se.period = e.period
             AND se.event_team_id = e.pp_team_id
             AND se.period_time_seconds BETWEEN e.period_time_seconds AND e.period_time_seconds + 30
            LEFT JOIN shots s ON s.event_id = se.event_id
            GROUP BY e.possession_id
        ),
        team_tendency AS (
            SELECT
                p.team_id AS pp_team_id,
                AVG(CASE WHEN p.entry_type = 'CONTROLLED' THEN 1.0 ELSE 0.0 END) AS controlled_entry_tendency
            FROM possessions p
            JOIN games g ON p.game_id = g.game_id
            WHERE p.strength = '5v4'
              AND p.entry_type IN ('CONTROLLED', 'DUMP_IN')
              AND p.team_id = CASE
                    WHEN split_part(p.strength, 'v', 1)::int > split_part(p.strength, 'v', 2)::int THEN g.away_team_id
                    WHEN split_part(p.strength, 'v', 2)::int > split_part(p.strength, 'v', 1)::int THEN g.home_team_id
              END
            GROUP BY p.team_id
        )
        SELECT
            e.*,
            COALESCE(p.linked_pk_forecheckers, 0) AS linked_pk_forecheckers,
            CASE
                WHEN COALESCE(p.linked_pk_forecheckers, 0) <= 0 THEN 'Passive'
                WHEN COALESCE(p.linked_pk_forecheckers, 0) = 1 THEN 'Standard'
                ELSE 'Aggressive'
            END AS forecheck_structure,
            COALESCE(s.xga_30, 0) AS xga_30,
            COALESCE(s.shots_30, 0) AS shots_30,
            COALESCE(s.rush_shots, 0) AS rush_shots,
            COALESCE(t.controlled_entry_tendency, 0) AS controlled_entry_tendency,
            CASE WHEN COALESCE(t.controlled_entry_tendency, 0) >= 0.5 THEN 'carry_in_heavy' ELSE 'dump_in_heavy' END AS opponent_tendency
        FROM pp_entries e
        LEFT JOIN pressure_proxy p ON p.possession_id = e.possession_id
        LEFT JOIN shots_30 s ON s.possession_id = e.possession_id
        LEFT JOIN team_tendency t ON t.pp_team_id = e.pp_team_id
        """
        logger.info("Fetching PK forecheck structure data...")
        self.data = self.db.query_to_df(query)
        logger.info("Model 4 sample: %s PP entries", len(self.data))
        return self.data

    @staticmethod
    def _summary(group):
        seconds = group["duration_seconds"].astype(float).clip(lower=1).sum()
        return {
            "n_entries": int(len(group)),
            "controlled_entry_allowed_rate": float((group["entry_type"] == "CONTROLLED").mean()),
            "xga_30_per_entry": float(group["xga_30"].astype(float).mean()),
            "xga_60": float(group["xga_30"].astype(float).sum() / seconds * 60) if seconds > 0 else None,
            "odd_man_rush_rate_proxy": float((group["rush_shots"].astype(float) > 0).mean()),
        }

    def run(self):
        logger.info("=" * 60)
        logger.info("MODEL 4: Aggressive vs Passive PK Forecheck Structure")
        logger.info("=" * 60)
        data = self.fetch_data()

        rows = []
        for structure, group in data.groupby("forecheck_structure"):
            row = {"forecheck_structure": structure, **self._summary(group)}
            row["xga_30_ci"] = bootstrap_ci_by_game(
                group, "game_id", lambda x: x["xga_30"].astype(float).mean(), n_bootstrap=500
            )
            rows.append(row)

        tendency_rows = []
        for keys, group in data.groupby(["opponent_tendency", "forecheck_structure"]):
            tendency, structure = keys
            tendency_rows.append(
                {"opponent_tendency": tendency, "forecheck_structure": structure, **self._summary(group)}
            )

        results = add_timestamp(
            {
                "model": "Aggressive vs Passive PK Forecheck Structure",
                "summary_by_structure": rows,
                "summary_by_opponent_tendency": tendency_rows,
                "sample": {"n_entries": int(len(data))},
                "caveats": [
                    "Forechecker count is a pressure proxy from recent PK-linked events, not true player positioning",
                    "event_players is treated as event-linked/on-ice context but does not include tracking coordinates",
                    "xGA/60 uses observed possession duration because true TOI is unavailable",
                    "Odd-man rush rate depends on sparse text descriptions and is likely undercounted",
                    "This is descriptive, not causal",
                ],
            }
        )
        results["output_file"] = export_json(results, "model4_pk_forecheck_structure.json")
        logger.info("Model 4 output: %s", results["output_file"])
        return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
    db = DatabaseConnection()
    db.connect()
    try:
        PkForecheckStructureModel(db).run()
    finally:
        db.close()
