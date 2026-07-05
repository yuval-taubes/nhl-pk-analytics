"""Dynamic player tags from MoneyPuck season aggregates."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from models.model_utils import add_timestamp, export_json
from models_v2.common import records
from moneypuck.features import per60, rate


logger = logging.getLogger(__name__)


class PlayerTaggingModel:
    """Attach explainable scouting tags to PK player-season profiles."""

    TAG_RULES_VERSION = "player_tags_v1"

    def __init__(self, db_connection):
        self.db = db_connection
        self.data = pd.DataFrame()

    def fetch_data(self):
        query = """
        SELECT
            player_id,
            name,
            position,
            team,
            season,
            ice_time,
            games_played,
            i_f_x_goals,
            i_f_shot_attempts,
            on_ice_f_x_goals,
            on_ice_a_x_goals,
            on_ice_f_shot_attempts,
            on_ice_a_shot_attempts,
            shots_blocked_by_player,
            penalties,
            penalties_drawn
        FROM mp_skaters_season
        WHERE situation = '4on5'
          AND ice_time IS NOT NULL
          AND ice_time > 0
        """
        logger.info("Fetching MoneyPuck PK skater rows for player tags...")
        self.data = self.db.query_to_df(query)
        logger.info("Player-tag source rows: %s", len(self.data))
        return self.data

    def run(self):
        self.fetch_data()
        profiles = self.build_profiles(self.player_seasons())
        latest = self.latest_profiles(profiles)

        results = add_timestamp(
            {
                "model": "MoneyPuck Dynamic PK Player Tags",
                "tag_rules_version": self.TAG_RULES_VERSION,
                "player_profiles": records(profiles),
                "latest_player_passports": records(latest),
                "tag_dictionary": self.tag_dictionary(),
                "seasons": sorted([int(season) for season in profiles["season"].dropna().unique()], reverse=True) if not profiles.empty else [],
                "source_lineage": {
                    "source": "MoneyPuck mp_skaters_season rows filtered to 4on5",
                    "feature_layer": "player-season aggregation, per-60 rates, season percentiles, empirical shrinkage",
                    "tag_layer": "centralized Python rules in models_v2/player_tags.py",
                    "ui_contract": "API exposes compact playerTagProfiles; frontend renders explanations only",
                },
                "sample": {
                    "skater_source_rows": int(len(self.data)),
                    "player_profiles": int(len(profiles)),
                    "minimum_seconds_for_profile": 300,
                    "trusted_seconds": 1800,
                },
                "caveats": [
                    "Tags are inferred from public MoneyPuck season aggregates, not tracking data.",
                    "A fired tag means the rule threshold was met; it is not a complete scouting grade.",
                    "Player roles can change by season and team, so current-season filters matter.",
                ],
            }
        )
        results["output_file"] = export_json(results, "model_v2_player_tags.json")
        return results

    def player_seasons(self):
        rows = []
        for keys, group in self.data.groupby(["season", "player_id", "name", "position"]):
            season, player_id, name, position = keys
            ice_time = group["ice_time"].astype(float).sum()
            if ice_time < 300:
                continue

            on_f = group["on_ice_f_x_goals"].astype(float).sum()
            on_a = group["on_ice_a_x_goals"].astype(float).sum()
            attempts_for = group["on_ice_f_shot_attempts"].astype(float).sum()
            attempts_against = group["on_ice_a_shot_attempts"].astype(float).sum()
            indiv_xg = group["i_f_x_goals"].astype(float).sum()
            penalties_net = group["penalties_drawn"].astype(float).sum() - group["penalties"].astype(float).sum()
            relevant_events = attempts_for + attempts_against + group["shots_blocked_by_player"].astype(float).sum()
            relevant_events += group["penalties"].astype(float).sum() + group["penalties_drawn"].astype(float).sum()
            rows.append(
                {
                    "player_id": int(player_id),
                    "name": name,
                    "position": position,
                    "season": int(season),
                    "teams": ", ".join(sorted(group["team"].dropna().unique())),
                    "ice_time": float(ice_time),
                    "games_played": int(group["games_played"].astype(float).max()),
                    "on_ice_sh_xg_for_per60": per60(on_f, ice_time),
                    "on_ice_xga_per60": per60(on_a, ice_time),
                    "two_way_net_xg_per60": per60(on_f - on_a, ice_time),
                    "individual_sh_xg_per60": per60(indiv_xg, ice_time),
                    "shot_attempt_share": rate(attempts_for, attempts_for + attempts_against),
                    "relevant_event_count": int(relevant_events),
                    "blocks_per60": per60(group["shots_blocked_by_player"].astype(float).sum(), ice_time),
                    "penalty_draw_minus_take_per60": per60(penalties_net, ice_time),
                }
            )
        return pd.DataFrame(rows)

    def build_profiles(self, summary):
        if summary.empty:
            return summary

        tagged = []
        for season, season_df in summary.groupby("season"):
            frame = season_df.copy()
            league_mean = float(frame["two_way_net_xg_per60"].mean())
            league_sd = float(frame["two_way_net_xg_per60"].std(ddof=0) or 0.75)
            frame["sample_weight"] = frame["ice_time"].astype(float) / (frame["ice_time"].astype(float) + 1800.0)
            frame["true_talent_pk_impact_per60"] = league_mean + frame["sample_weight"] * (
                frame["two_way_net_xg_per60"].astype(float) - league_mean
            )
            frame["impact_uncertainty"] = np.maximum(0.18, league_sd * (1 - frame["sample_weight"] + 0.18))
            for column in [
                "on_ice_xga_per60",
                "on_ice_sh_xg_for_per60",
                "true_talent_pk_impact_per60",
                "individual_sh_xg_per60",
                "shot_attempt_share",
                "blocks_per60",
                "penalty_draw_minus_take_per60",
            ]:
                frame[f"{column}_percentile"] = frame[column].rank(pct=True)

            for _, row in frame.iterrows():
                tags = self.tags_for_player(row)
                sample = self.sample_context(row, tags)
                tagged.append(
                    {
                        **row.to_dict(),
                        "trust_level": sample["trust_level"],
                        "sample_trust": sample["sample_trust"],
                        "sample_trust_label": sample["sample_trust_label"],
                        "sample_trust_sentence": sample["sample_trust_sentence"],
                        "supporting_signal_count": sample["supporting_signal_count"],
                        "rate_sensitive_tag_count": sample["rate_sensitive_tag_count"],
                        "tags": tags,
                        "top_strengths": [tag for tag in tags if tag["category"] == "strength"][:3],
                        "main_risks": [tag for tag in tags if tag["category"] == "risk"][:3],
                        "summary_sentence": self.summary_sentence(row, tags),
                    }
                )
        output = pd.DataFrame(tagged)
        return output.sort_values(["season", "trust_level", "true_talent_pk_impact_per60"], ascending=[False, True, False])

    def tags_for_player(self, row):
        tags = []
        add = tags.append
        sample_note = self.sample_note(row)

        if row["ice_time"] >= 1800:
            add(
                self.tag(
                    "trusted_sample",
                    "Trusted sample",
                    "trust",
                    self.sample_confidence(row),
                    f"{row['name']} has {self.minutes(row)} short-handed minutes in this season sample.",
                    {"ice_time_seconds": row["ice_time"], "sample_weight": row["sample_weight"]},
                    sample_note,
                    "higher",
                    row.get("sample_weight"),
                )
            )
        elif row["ice_time"] < 600:
            add(
                self.tag(
                    "do_not_overread",
                    "Do not overread",
                    "trust",
                    self.sample_confidence(row),
                    f"{row['name']} has a small 4-on-5 sample, so the profile is mostly a watch-list signal.",
                    {"ice_time_seconds": row["ice_time"], "impact_uncertainty": row["impact_uncertainty"]},
                    sample_note,
                    "lower",
                    row.get("sample_weight"),
                )
            )

        if row["ice_time"] < 1200 and row["true_talent_pk_impact_per60_percentile"] >= 0.75:
            add(
                self.tag(
                    "interesting_but_noisy",
                    "Interesting but noisy",
                    "trust",
                    self.sample_confidence(row),
                    "The adjusted impact is strong, but the sample is not large enough to treat as stable.",
                    {
                        "true_talent_pk_impact_per60": row["true_talent_pk_impact_per60"],
                        "true_talent_percentile": row["true_talent_pk_impact_per60_percentile"],
                        "ice_time_seconds": row["ice_time"],
                    },
                    sample_note,
                    "higher",
                    row["true_talent_pk_impact_per60_percentile"],
                )
            )

        if row["position"] != "D" and row["ice_time"] >= 600 and row["on_ice_xga_per60_percentile"] <= 0.35:
            add(
                self.tag(
                    "low_event_pk_forward",
                    "Low-event PK forward",
                    "strength",
                    self.confidence(row),
                    "Opponent shot quality stayed low while this forward was on the ice at 4-on-5.",
                    {
                        "on_ice_xga_per60": row["on_ice_xga_per60"],
                        "xga_percentile_lower_is_better": row["on_ice_xga_per60_percentile"],
                    },
                    sample_note,
                    "lower",
                    row["on_ice_xga_per60_percentile"],
                )
            )

        if row["ice_time"] >= 600 and (
            row["individual_sh_xg_per60_percentile"] >= 0.75 or row["on_ice_sh_xg_for_per60_percentile"] >= 0.75
        ):
            add(
                self.tag(
                    "counterattack_pressure_valve",
                    "Counterattack pressure valve",
                    "style",
                    self.confidence(row),
                    "This player showed above-average short-handed shot-quality creation.",
                    {
                        "individual_sh_xg_per60": row["individual_sh_xg_per60"],
                        "on_ice_sh_xg_for_per60": row["on_ice_sh_xg_for_per60"],
                    },
                    sample_note,
                    "higher",
                    max(row["individual_sh_xg_per60_percentile"], row["on_ice_sh_xg_for_per60_percentile"]),
                )
            )

        if row["position"] == "D" and row["ice_time"] >= 600 and row["blocks_per60_percentile"] >= 0.75:
            add(
                self.tag(
                    "block_and_clear_defender",
                    "Block-and-clear defender",
                    "strength",
                    self.confidence(row),
                    "This defender blocked shots at a high rate in the 4-on-5 sample.",
                    {"blocks_per60": row["blocks_per60"], "blocks_percentile": row["blocks_per60_percentile"]},
                    sample_note,
                    "higher",
                    row["blocks_per60_percentile"],
                )
            )

        if row["ice_time"] >= 600 and row["penalty_draw_minus_take_per60_percentile"] <= 0.20:
            add(
                self.tag(
                    "penalty_risk",
                    "Penalty risk",
                    "risk",
                    self.confidence(row),
                    "Penalties taken outweighed penalties drawn relative to the league sample.",
                    {
                        "penalty_draw_minus_take_per60": row["penalty_draw_minus_take_per60"],
                        "penalty_net_percentile": row["penalty_draw_minus_take_per60_percentile"],
                    },
                    sample_note,
                    "higher",
                    row["penalty_draw_minus_take_per60_percentile"],
                )
            )

        return tags

    def tag(self, tag_id, label, category, confidence, reason, metrics, sample_note, higher_is_better, percentile):
        tag_strength = self.tag_strength(percentile, higher_is_better == "higher")
        return {
            "tag_id": tag_id,
            "label": label,
            "category": category,
            "confidence": confidence,
            "sample_confidence": confidence,
            "tag_strength": tag_strength,
            "priority_label": self.priority_label(tag_strength, category),
            "reason": reason,
            "metrics": self.clean_metrics(metrics),
            "sample_size_note": sample_note,
            "higher_is_better": higher_is_better == "higher",
            "league_percentile": None if percentile is None or pd.isna(percentile) else float(percentile),
            "caveat": "Inferred from public MoneyPuck season aggregates; no tracking or manual video label is implied.",
        }

    def clean_metrics(self, metrics):
        cleaned = {}
        for key, value in metrics.items():
            if value is None or pd.isna(value):
                cleaned[key] = None
            else:
                cleaned[key] = float(value)
        return cleaned

    def confidence(self, row):
        return self.sample_confidence(row)

    def sample_confidence(self, row):
        minutes = float(row["ice_time"]) / 60
        if minutes >= 150 and row["impact_uncertainty"] <= 0.75:
            return "high"
        if minutes >= 80:
            return "medium"
        return "low"

    def sample_bucket(self, row):
        minutes = float(row["ice_time"]) / 60
        if minutes < 40:
            return "low_sample", "Low sample"
        if minutes < 80:
            return "limited_sample", "Limited sample"
        if minutes < 150:
            return "medium_sample", "Medium sample"
        return "strong_sample", "Strong sample"

    def sample_context(self, row, tags):
        sample_trust, sample_label = self.sample_bucket(row)
        minutes = float(row["ice_time"]) / 60
        supporting_tags = [tag for tag in tags if tag["category"] != "trust"]
        supporting_signal_count = len(supporting_tags)
        rate_sensitive_tag_count = sum(1 for tag in supporting_tags if tag["category"] in {"strength", "style", "risk"})
        event_count = int(row.get("relevant_event_count", 0) or 0)
        if sample_trust == "low_sample":
            trust_level = "low"
            sentence = f"Low sample: only {minutes:.0f} PK minutes, treat as directional."
        elif sample_trust == "limited_sample":
            trust_level = "low" if rate_sensitive_tag_count else "medium"
            sentence = f"Limited sample: {minutes:.0f} PK minutes and {supporting_signal_count} supporting tag events."
        elif sample_trust == "medium_sample":
            trust_level = "medium"
            sentence = f"Medium signal: {minutes:.0f} PK minutes and {supporting_signal_count} supporting tag events."
        else:
            trust_level = "high" if supporting_signal_count >= 2 and row["impact_uncertainty"] <= 0.75 else "medium"
            sentence = f"Strong sample: {minutes:.0f} PK minutes, {event_count} relevant events, and {supporting_signal_count} supporting tag events."
        return {
            "trust_level": trust_level,
            "sample_trust": sample_trust,
            "sample_trust_label": sample_label,
            "sample_trust_sentence": sentence,
            "supporting_signal_count": supporting_signal_count,
            "rate_sensitive_tag_count": rate_sensitive_tag_count,
        }

    def trust_level(self, row):
        return self.sample_context(row, [])["trust_level"]

    def tag_strength(self, percentile, higher_is_better):
        if percentile is None or pd.isna(percentile):
            return "medium"
        score = float(percentile) if higher_is_better else 1 - float(percentile)
        if score >= 0.8:
            return "strong"
        if score >= 0.6:
            return "medium"
        return "weak"

    def priority_label(self, tag_strength, category):
        if category == "trust":
            return "sample"
        if tag_strength == "strong":
            return "primary"
        if tag_strength == "medium":
            return "supporting"
        return "watch"

    def legacy_trust_level(self, row):
        if row["ice_time"] < 600:
            return "low"
        if row["ice_time"] >= 3600 and row["impact_uncertainty"] <= 0.75:
            return "high"
        return "medium"

    def sample_note(self, row):
        return f"{self.minutes(row)} at 4-on-5 in {int(row['season'])}."

    def minutes(self, row):
        return f"{float(row['ice_time']) / 60:.0f} minutes"

    def summary_sentence(self, row, tags):
        strength_labels = [tag["label"].lower() for tag in tags if tag["category"] in {"strength", "style"}]
        risk_labels = [tag["label"].lower() for tag in tags if tag["category"] == "risk"]
        if not strength_labels and not risk_labels:
            return f"{row['name']} is a {self.trust_level(row)}-trust PK profile with no major first-pass tag."
        sentence = f"{row['name']} profiles as {', '.join(strength_labels[:2]) or 'a watch-list PK skater'}"
        if risk_labels:
            sentence += f", with {risk_labels[0]} flagged"
        return sentence + "."

    def latest_profiles(self, profiles):
        if profiles.empty:
            return profiles
        latest_season = profiles["season"].max()
        latest = profiles[profiles["season"] == latest_season].copy()
        latest["tag_count"] = latest["tags"].apply(len)
        return latest.sort_values(["tag_count", "true_talent_pk_impact_per60"], ascending=[False, False]).head(80)

    def tag_dictionary(self):
        return [
            {"tag_id": "trusted_sample", "category": "trust", "meaning": "Large enough 4-on-5 sample to read with more confidence."},
            {"tag_id": "do_not_overread", "category": "trust", "meaning": "Small sample; keep as a watch-list profile."},
            {"tag_id": "interesting_but_noisy", "category": "trust", "meaning": "Strong adjusted result with limited minutes."},
            {"tag_id": "low_event_pk_forward", "category": "strength", "meaning": "Forward on-ice xGA stayed low relative to the league season."},
            {"tag_id": "counterattack_pressure_valve", "category": "style", "meaning": "Short-handed shot-quality creation was above league norms."},
            {"tag_id": "block_and_clear_defender", "category": "strength", "meaning": "Defenseman shot-blocking rate stood out."},
            {"tag_id": "penalty_risk", "category": "risk", "meaning": "Penalty drawn-minus-taken rate was poor relative to the league season."},
        ]
