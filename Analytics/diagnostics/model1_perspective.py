"""
Diagnostic report for Model 1 possession perspective.

Checks whether special-teams entry possessions are owned by the power-play or
penalty-kill team before Model 1 interprets xG as xG against the PK.
"""

import logging
import os
from datetime import datetime

from db import DatabaseConnection

logger = logging.getLogger(__name__)


def diagnose_model1_perspective(db, sample_size=20, output_dir="runs"):
    os.makedirs(output_dir, exist_ok=True)

    summary_query = """
    WITH labeled AS (
        SELECT
            p.possession_id,
            p.game_id,
            p.strength,
            p.entry_type,
            p.team_id,
            p.xg_sum,
            pp.abbreviation AS pp_team,
            pk.abbreviation AS pk_team,
            CASE
                WHEN p.team_id = pp.team_id THEN 'PP possession'
                WHEN p.team_id = pk.team_id THEN 'PK possession'
                ELSE 'unknown'
            END AS perspective
        FROM possessions p
        JOIN games g ON p.game_id = g.game_id
        JOIN teams pp ON pp.team_id = CASE
            WHEN split_part(p.strength, 'v', 1)::int > split_part(p.strength, 'v', 2)::int THEN g.away_team_id
            WHEN split_part(p.strength, 'v', 2)::int > split_part(p.strength, 'v', 1)::int THEN g.home_team_id
        END
        JOIN teams pk ON pk.team_id = CASE
            WHEN split_part(p.strength, 'v', 1)::int < split_part(p.strength, 'v', 2)::int THEN g.away_team_id
            WHEN split_part(p.strength, 'v', 2)::int < split_part(p.strength, 'v', 1)::int THEN g.home_team_id
        END
        WHERE p.strength IN ('4v5', '3v5', '3v4', '5v4', '5v3', '4v3')
          AND p.entry_type IN ('CONTROLLED', 'DUMP_IN')
          AND p.xg_sum IS NOT NULL
    )
    SELECT
        strength,
        perspective,
        entry_type,
        COUNT(*) AS n,
        AVG(xg_sum) AS avg_xg
    FROM labeled
    GROUP BY strength, perspective, entry_type
    ORDER BY strength, perspective, entry_type
    """

    sample_query = """
    WITH labeled AS (
        SELECT
            p.possession_id,
            p.game_id,
            p.strength,
            p.entry_type,
            p.end_type,
            p.duration_seconds,
            p.shot_count,
            p.goal_count,
            p.xg_sum,
            own.abbreviation AS possession_team,
            pp.abbreviation AS pp_team,
            pk.abbreviation AS pk_team,
            e.period,
            e.period_time_seconds,
            e.zone AS start_zone,
            CASE
                WHEN p.team_id = pp.team_id THEN 'PP possession'
                WHEN p.team_id = pk.team_id THEN 'PK possession'
                ELSE 'unknown'
            END AS perspective
        FROM possessions p
        JOIN games g ON p.game_id = g.game_id
        JOIN events e ON p.start_event_id = e.event_id
        JOIN teams own ON own.team_id = p.team_id
        JOIN teams pp ON pp.team_id = CASE
            WHEN split_part(p.strength, 'v', 1)::int > split_part(p.strength, 'v', 2)::int THEN g.away_team_id
            WHEN split_part(p.strength, 'v', 2)::int > split_part(p.strength, 'v', 1)::int THEN g.home_team_id
        END
        JOIN teams pk ON pk.team_id = CASE
            WHEN split_part(p.strength, 'v', 1)::int < split_part(p.strength, 'v', 2)::int THEN g.away_team_id
            WHEN split_part(p.strength, 'v', 2)::int < split_part(p.strength, 'v', 1)::int THEN g.home_team_id
        END
        WHERE p.strength IN ('4v5', '3v5', '3v4', '5v4', '5v3', '4v3')
          AND p.entry_type IN ('CONTROLLED', 'DUMP_IN')
          AND p.xg_sum IS NOT NULL
        ORDER BY p.game_id, e.event_idx
        LIMIT %s
    )
    SELECT * FROM labeled
    """

    summary = db.query_to_df(summary_query)
    sample = db.query_to_df(sample_query, (sample_size,))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(output_dir, f"model1_perspective_{timestamp}.md")

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("# Model 1 Perspective Diagnostic\n\n")
        f.write("Strength is stored as away skaters v home skaters.\n\n")
        f.write("## Ownership Summary\n\n")
        f.write("```text\n")
        f.write(summary.to_string(index=False))
        f.write("\n```")
        f.write("\n\n## Sample Possessions\n\n")
        f.write("```text\n")
        f.write(sample.to_string(index=False))
        f.write("\n```")
        f.write("\n")

    logger.info("Model 1 perspective report: %s", output_file)
    logger.info("\n%s", summary.to_string(index=False))

    return {
        "summary": summary,
        "sample": sample,
        "output_file": output_file,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
    db = DatabaseConnection()
    db.connect()
    try:
        diagnose_model1_perspective(db)
    finally:
        db.close()
