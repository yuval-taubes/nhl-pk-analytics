"""Behavior tests for dynamic MoneyPuck player tags."""

from __future__ import annotations

import unittest

try:
    import pandas as pd
    from models_v2.player_tags import PlayerTaggingModel
except ModuleNotFoundError as exc:
    pd = None
    PlayerTaggingModel = None
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None


def player_row(name, position, ice_time, xga, sh_xg, indiv_xg, blocks, penalty_net):
    return {
        "season": 2025,
        "player_id": abs(hash(name)) % 100000,
        "name": name,
        "position": position,
        "teams": "TST",
        "ice_time": ice_time,
        "games_played": 20,
        "on_ice_sh_xg_for_per60": sh_xg,
        "on_ice_xga_per60": xga,
        "two_way_net_xg_per60": sh_xg - xga,
        "individual_sh_xg_per60": indiv_xg,
        "shot_attempt_share": 0.25,
        "relevant_event_count": int(max(1, ice_time // 30)),
        "blocks_per60": blocks,
        "penalty_draw_minus_take_per60": penalty_net,
    }


class PlayerTaggingTests(unittest.TestCase):
    def setUp(self):
        if IMPORT_ERROR is not None:
            self.skipTest(f"optional analytics dependency unavailable: {IMPORT_ERROR}")

    def test_tag_profiles_include_auditable_tag_shape(self):
        model = PlayerTaggingModel(None)
        summary = pd.DataFrame(
            [
                player_row("Quiet Forward", "C", 2400, 1.0, 0.4, 0.1, 1.0, 0.0),
                player_row("High Event Forward", "C", 2400, 4.0, 2.0, 1.0, 1.0, -0.1),
                player_row("Block Defender", "D", 2400, 2.0, 0.2, 0.0, 6.0, -0.2),
                player_row("Penalty Risk", "R", 2400, 2.2, 0.2, 0.0, 1.0, -2.0),
            ]
        )

        profiles = model.build_profiles(summary)
        quiet = profiles[profiles["name"] == "Quiet Forward"].iloc[0]
        tags = quiet["tags"]

        self.assertTrue(any(tag["tag_id"] == "low_event_pk_forward" for tag in tags))
        self.assertIn("metrics", tags[0])
        self.assertIn("sample_size_note", tags[0])
        self.assertIn("caveat", tags[0])
        self.assertIn("tag_strength", tags[0])
        self.assertIn("sample_confidence", tags[0])

    def test_small_samples_get_do_not_overread(self):
        model = PlayerTaggingModel(None)
        summary = pd.DataFrame(
            [
                player_row("Tiny Sample", "C", 320, 1.0, 3.0, 2.0, 0.0, 0.0),
                player_row("Regular One", "C", 2400, 2.0, 0.5, 0.1, 1.0, 0.0),
                player_row("Regular Two", "D", 2400, 2.5, 0.4, 0.0, 2.0, -0.2),
            ]
        )

        profiles = model.build_profiles(summary)
        tiny = profiles[profiles["name"] == "Tiny Sample"].iloc[0]
        tag_ids = {tag["tag_id"] for tag in tiny["tags"]}

        self.assertIn("do_not_overread", tag_ids)
        self.assertEqual(tiny["trust_level"], "low")
        self.assertEqual(tiny["sample_trust"], "low_sample")
        self.assertIn("Low sample", tiny["sample_trust_sentence"])
        self.assertNotIn("rebound_cleanup", tag_ids)

    def test_sample_trust_is_separate_from_tag_strength(self):
        model = PlayerTaggingModel(None)
        summary = pd.DataFrame(
            [
                player_row("Twenty Five Minutes", "D", 1500, 1.0, 1.0, 0.2, 8.0, -2.0),
                player_row("Hundred Minute Forward", "C", 6540, 1.0, 0.8, 0.2, 1.0, 0.0),
                player_row("Regular Two", "D", 7200, 2.5, 0.4, 0.0, 2.0, -0.2),
                player_row("Regular Three", "C", 7200, 2.5, 0.4, 0.0, 2.0, -0.2),
            ]
        )

        profiles = model.build_profiles(summary)
        tiny = profiles[profiles["name"] == "Twenty Five Minutes"].iloc[0]
        regular = profiles[profiles["name"] == "Hundred Minute Forward"].iloc[0]

        self.assertEqual(tiny["sample_trust"], "low_sample")
        self.assertEqual(tiny["trust_level"], "low")
        self.assertEqual(regular["sample_trust"], "medium_sample")
        self.assertEqual(regular["trust_level"], "medium")
        self.assertTrue(all("tag_strength" in tag for tag in regular["tags"]))


if __name__ == "__main__":
    unittest.main()
