"""Adjusted next-shot pressure model for source-covered PK event states.

This is a diagnostic association model. It estimates whether the opponent
records the next shot attempt within ten seconds, with game-clustered standard
errors and measured contextual controls.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from diagnostics.shift_pk_exposure import markdown_table


REPORT_DIR = Path(__file__).resolve().parents[1] / "reports"
REPORT_PATH = REPORT_DIR / "latest_shift_pk_adjusted_pressure.md"
ESTIMATES_CSV = REPORT_DIR / "latest_shift_pk_adjusted_pressure_estimates.csv"
SENSITIVITY_CSV = REPORT_DIR / "latest_shift_pk_adjusted_pressure_sensitivity.csv"
CONTROL_PROXY_CSV = REPORT_DIR / "latest_shift_pk_pp_control_sensitivity.csv"
SUMMARY_JSON = REPORT_DIR / "latest_shift_pk_adjusted_pressure.json"
MODEL_RHS = (
    "C(shift_age_bucket, Treatment(reference='00-29')) "
    "+ shortest_rest_seconds + penalty_elapsed_seconds + period + score_diff "
    "+ C(zone) + C(current_event_type) + C(pk_team_id) + C(opponent_team_id)"
)
MODEL_FORMULA = f"next_shot_against_10 ~ {MODEL_RHS}"
CONTROL_PROXY_RHS = (
    "C(shift_age_bucket, Treatment(reference='00-29')) "
    "+ shortest_rest_seconds + penalty_elapsed_seconds + period + score_diff + C(current_event_type)"
)
BUCKET_ORDER = ["00-29", "30-44", "45-59", "60+"]


def shift_age_bucket(age):
    if age < 30:
        return "00-29"
    if age < 45:
        return "30-44"
    if age < 60:
        return "45-59"
    return "60+"


def load_model_data(db):
    return db.query_to_df(
        """
        WITH expanded AS (
            SELECT
                e.game_id,
                e.event_id,
                e.event_idx,
                e.period,
                e.period_time_seconds,
                e.period_time_seconds + 1200 * (e.period - 1) AS game_seconds,
                e.event_type AS current_event_type,
                COALESCE(e.zone, 'UNKNOWN') AS zone,
                e.event_team_id,
                side.pk_team_id,
                side.opponent_team_id,
                side.is_pk,
                CASE WHEN side.pk_team_id = g.home_team_id
                    THEN COALESCE(SUM(CASE WHEN e.event_type = 'goal' AND e.event_team_id = g.home_team_id THEN 1 ELSE 0 END)
                        OVER (PARTITION BY e.game_id, side.pk_team_id ORDER BY e.event_idx ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0)
                       - COALESCE(SUM(CASE WHEN e.event_type = 'goal' AND e.event_team_id = g.away_team_id THEN 1 ELSE 0 END)
                        OVER (PARTITION BY e.game_id, side.pk_team_id ORDER BY e.event_idx ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0)
                    ELSE COALESCE(SUM(CASE WHEN e.event_type = 'goal' AND e.event_team_id = g.away_team_id THEN 1 ELSE 0 END)
                        OVER (PARTITION BY e.game_id, side.pk_team_id ORDER BY e.event_idx ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0)
                       - COALESCE(SUM(CASE WHEN e.event_type = 'goal' AND e.event_team_id = g.home_team_id THEN 1 ELSE 0 END)
                        OVER (PARTITION BY e.game_id, side.pk_team_id ORDER BY e.event_idx ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0)
                END AS score_diff
            FROM events e
            JOIN games g ON g.game_id = e.game_id
            CROSS JOIN LATERAL (
                VALUES
                    (g.home_team_id, g.away_team_id, e.home_skaters < e.away_skaters),
                    (g.away_team_id, g.home_team_id, e.away_skaters < e.home_skaters)
            ) AS side(pk_team_id, opponent_team_id, is_pk)
        ), sequenced AS (
            SELECT
                expanded.*,
                LAG(is_pk, 1, FALSE) OVER (PARTITION BY game_id, pk_team_id ORDER BY event_idx) AS previous_is_pk,
                LEAD(current_event_type) OVER (PARTITION BY game_id, pk_team_id ORDER BY event_idx) AS next_event_type,
                LEAD(event_team_id) OVER (PARTITION BY game_id, pk_team_id ORDER BY event_idx) AS next_event_team_id,
                LEAD(game_seconds) OVER (PARTITION BY game_id, pk_team_id ORDER BY event_idx) AS next_game_seconds
            FROM expanded
        ), grouped AS (
            SELECT
                sequenced.*,
                SUM(CASE WHEN is_pk AND NOT previous_is_pk THEN 1 ELSE 0 END)
                    OVER (PARTITION BY game_id, pk_team_id ORDER BY event_idx) AS pk_group
            FROM sequenced
        ), pk_states AS (
            SELECT
                grouped.*,
                MIN(game_seconds) OVER (PARTITION BY game_id, pk_team_id, pk_group) AS pk_start_seconds
            FROM grouped
            WHERE is_pk
        ), shift_features AS (
            SELECT
                game_id,
                event_id,
                team_id AS pk_team_id,
                MAX(shift_age_seconds)::float AS oldest_shift_age_seconds,
                MIN(rest_before_shift_seconds)::float AS shortest_rest_seconds
            FROM pk_shift_player_event_features
            WHERE is_penalty_killing
            GROUP BY game_id, event_id, team_id
        )
        SELECT
            ps.game_id,
            ps.event_id,
            ps.pk_team_id,
            ps.opponent_team_id,
            ps.period,
            ps.zone,
            ps.current_event_type,
            GREATEST(-3, LEAST(3, ps.score_diff))::int AS score_diff,
            (ps.game_seconds - ps.pk_start_seconds)::float AS penalty_elapsed_seconds,
            sf.oldest_shift_age_seconds,
            sf.shortest_rest_seconds,
            CASE WHEN ps.event_team_id = ps.opponent_team_id AND ps.zone = 'OZ' THEN 1 ELSE 0 END::int AS pp_oz_control_proxy,
            CASE WHEN ps.next_event_team_id = ps.opponent_team_id
                      AND ps.next_event_type IN ('shot-on-goal', 'missed-shot', 'blocked-shot', 'goal')
                      AND ps.next_game_seconds - ps.game_seconds BETWEEN 0 AND 10
                 THEN 1 ELSE 0 END::int AS next_shot_against_10
            ,CASE WHEN ps.next_event_team_id = ps.opponent_team_id
                      AND ps.next_event_type IN ('shot-on-goal', 'missed-shot', 'blocked-shot', 'goal')
                      AND ps.next_game_seconds - ps.game_seconds BETWEEN 0 AND 5
                 THEN 1 ELSE 0 END::int AS next_shot_against_5
            ,CASE WHEN ps.next_event_team_id = ps.opponent_team_id
                      AND ps.next_event_type IN ('shot-on-goal', 'missed-shot', 'blocked-shot', 'goal')
                      AND ps.next_game_seconds - ps.game_seconds BETWEEN 0 AND 15
                 THEN 1 ELSE 0 END::int AS next_shot_against_15
        FROM pk_states ps
        JOIN shift_features sf
          ON sf.game_id = ps.game_id
         AND sf.event_id = ps.event_id
         AND sf.pk_team_id = ps.pk_team_id
        WHERE ps.current_event_type <> 'goal'
          AND ps.next_game_seconds IS NOT NULL
        ORDER BY ps.game_id, ps.event_id, ps.pk_team_id
        """
    )


def prepare_data(data):
    import pandas as pd

    result = data.dropna(
        subset=["oldest_shift_age_seconds", "shortest_rest_seconds", "penalty_elapsed_seconds", "next_shot_against_10"]
    ).copy()
    result["shift_age_bucket"] = pd.Categorical(
        result["oldest_shift_age_seconds"].map(shift_age_bucket), categories=BUCKET_ORDER, ordered=True
    )
    result["zone"] = result["zone"].fillna("UNKNOWN").astype(str)
    result["current_event_type"] = result["current_event_type"].fillna("UNKNOWN").astype(str)
    return result


def fit_model(data, outcome="next_shot_against_10", rhs=MODEL_RHS):
    import statsmodels.api as sm
    import statsmodels.formula.api as smf

    model = smf.glm(f"{outcome} ~ {rhs}", data=data, family=sm.families.Binomial())
    return model.fit(cov_type="cluster", cov_kwds={"groups": data["game_id"]})


def adjusted_bucket_estimates(model, data):
    import numpy as np
    import pandas as pd

    rows = []
    for bucket in BUCKET_ORDER:
        counterfactual = data.copy()
        counterfactual["shift_age_bucket"] = pd.Categorical(
            [bucket] * len(counterfactual), categories=BUCKET_ORDER, ordered=True
        )
        probability = float(np.mean(model.predict(counterfactual)))
        rows.append({"shift_age_bucket": bucket, "adjusted_next_shot_probability": probability, "adjusted_per_100_events": 100 * probability})
    return pd.DataFrame(rows)


def coefficient_table(model):
    import numpy as np
    import pandas as pd

    rows = [
        {
            "shift_age_bucket": "00-29",
            "odds_ratio_vs_00_29": 1.0,
            "or_ci_low": None,
            "or_ci_high": None,
            "p_value": None,
        }
    ]
    for bucket in BUCKET_ORDER[1:]:
        key = f"C(shift_age_bucket, Treatment(reference='00-29'))[T.{bucket}]"
        coefficient = float(model.params[key])
        low, high = model.conf_int().loc[key]
        rows.append(
            {
                "shift_age_bucket": bucket,
                "odds_ratio_vs_00_29": float(np.exp(coefficient)),
                "or_ci_low": float(np.exp(low)),
                "or_ci_high": float(np.exp(high)),
                "p_value": float(model.pvalues[key]),
            }
        )
    return pd.DataFrame(rows)


def sensitivity_table(data):
    import pandas as pd

    rows = []
    for horizon in (5, 10, 15):
        outcome = f"next_shot_against_{horizon}"
        model = fit_model(data, outcome)
        adjusted = adjusted_bucket_estimates(model, data)
        coefficients = coefficient_table(model)
        combined = adjusted.merge(coefficients, on="shift_age_bucket", how="left")
        for row in combined.to_dict("records"):
            rows.append({"horizon_seconds": horizon, **row})
    return pd.DataFrame(rows)


def control_proxy_sensitivity(data):
    subset = data[data["pp_oz_control_proxy"] == 1].copy()
    model = fit_model(subset, rhs=CONTROL_PROXY_RHS)
    adjusted = adjusted_bucket_estimates(model, subset)
    coefficients = coefficient_table(model)
    return subset, model, adjusted.merge(coefficients, on="shift_age_bucket", how="left")


def write_report(data, model, adjusted, coefficients, sensitivity, control_subset, control_model, control_estimates):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    estimates = adjusted.merge(coefficients, on="shift_age_bucket", how="left")
    estimates.to_csv(ESTIMATES_CSV, index=False)
    sensitivity.to_csv(SENSITIVITY_CSV, index=False)
    control_estimates.to_csv(CONTROL_PROXY_CSV, index=False)
    SUMMARY_JSON.write_text(
        json.dumps(
            {
                "generatedAt": datetime.now().isoformat(timespec="seconds"),
                "status": "promising_adjusted_association",
                "rows": len(data),
                "games": int(data["game_id"].nunique()),
                "outcomes": int(data["next_shot_against_10"].sum()),
                "horizonSeconds": 10,
                "estimates": [
                    {
                        "bucket": row["shift_age_bucket"],
                        "adjustedProbability": row["adjusted_next_shot_probability"],
                        "adjustedPer100Events": row["adjusted_per_100_events"],
                    }
                    for row in adjusted.to_dict("records")
                ],
                "controlProxy": {
                    "definition": "Event explicitly owned by the PP team in its offensive zone",
                    "rows": len(control_subset),
                    "games": int(control_subset["game_id"].nunique()),
                    "estimates": [
                        {
                            "bucket": row["shift_age_bucket"],
                            "adjustedProbability": row["adjusted_next_shot_probability"],
                            "adjustedPer100Events": row["adjusted_per_100_events"],
                        }
                        for row in control_estimates.to_dict("records")
                    ],
                },
                "caveat": "Adjusted association, not a causal fatigue estimate; tracking, deployment intent, and exact possession state remain unobserved.",
            },
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    report = [
        "# Adjusted Source-Covered PK Pressure",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        f"Rows: `{len(data)}`",
        f"Games: `{data['game_id'].nunique()}`",
        f"PK teams: `{data['pk_team_id'].nunique()}`",
        f"Next-shot outcomes within 10 seconds: `{int(data['next_shot_against_10'].sum())}`",
        f"Outcome rate: `{data['next_shot_against_10'].mean():.2%}`",
        f"Model converged: `{bool(model.converged)}`",
        f"Game clusters: `{data['game_id'].nunique()}`",
        f"Estimated parameters: `{len(model.params)}`",
        f"Rows per parameter: `{len(data) / len(model.params):.1f}`",
        "",
        "## Adjusted Shift-Age Estimates",
        "",
        markdown_table(estimates.to_dict("records"), list(estimates.columns)),
        "",
        "## Horizon Sensitivity",
        "",
        markdown_table(
            sensitivity.to_dict("records"),
            ["horizon_seconds", "shift_age_bucket", "adjusted_per_100_events", "odds_ratio_vs_00_29", "or_ci_low", "or_ci_high", "p_value"],
        ),
        "",
        "## PP Offensive-Zone Control Proxy",
        "",
        f"Rows: `{len(control_subset)}`; games: `{control_subset['game_id'].nunique()}`; outcomes: `{int(control_subset['next_shot_against_10'].sum())}`; model converged: `{bool(control_model.converged)}`.",
        "",
        markdown_table(control_estimates.to_dict("records"), list(control_estimates.columns)),
        "",
        "This sensitivity keeps only events explicitly owned by the PP team in its offensive zone. It is a conservative high-confidence control proxy, not a complete possession definition. "
        "The reduced model controls rest, penalty elapsed time, period, score, and current event type with game-clustered uncertainty; team/opponent effects are omitted to keep the smaller fit estimable.",
        "",
        "## Model",
        "",
        f"`{MODEL_FORMULA}`",
        "",
        "The outcome is whether the opponent records the next shot attempt within ten seconds of the current source-covered PK event. "
        "Adjusted probabilities are average model predictions after setting every row to each shift-age bucket while preserving its observed controls. Standard errors are clustered by game.",
        "",
        "## Limits",
        "",
        "This is an adjusted association, not a causal fatigue estimate. It controls measured penalty elapsed time, shortest game-clock shift gap, period, running score differential, current event zone/type, PK team, and opponent. The rest control excludes real intermission duration and is not wall-clock recovery. "
        "It does not observe player positioning, tactical formation, deployment intent, exact possession state, substitutions between recorded events, or unmeasured opponent quality within team fixed effects.",
        "",
        f"Model fit: AIC `{model.aic:.1f}`; residual degrees of freedom `{int(model.df_resid)}`. "
        "The result is labeled a promising adjusted association only; causal language remains blocked.",
        "",
    ]
    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Fit adjusted source-covered PK pressure diagnostic.")
    parser.parse_args()
    from db import DatabaseConnection

    db = DatabaseConnection()
    db.connect()
    try:
        data = prepare_data(load_model_data(db))
    finally:
        db.close()
    model = fit_model(data)
    adjusted = adjusted_bucket_estimates(model, data)
    coefficients = coefficient_table(model)
    sensitivity = sensitivity_table(data)
    control_subset, control_model, control_estimates = control_proxy_sensitivity(data)
    write_report(data, model, adjusted, coefficients, sensitivity, control_subset, control_model, control_estimates)
    print(f"Wrote {REPORT_PATH}")
    print(f"Wrote {ESTIMATES_CSV}")
    print(f"Wrote {SENSITIVITY_CSV}")
    print(f"Wrote {CONTROL_PROXY_CSV}")
    print(f"Wrote {SUMMARY_JSON}")


if __name__ == "__main__":
    main()
