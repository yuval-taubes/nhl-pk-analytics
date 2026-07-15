"""Regression tests for the shift availability scanner helpers."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "Analytics"))

import diagnostics.scan_shift_availability as scanner
from diagnostics.scan_shift_availability import SOURCE_STATUS_MAP, parse_game_ids, scan_games, select_games


class ShiftAvailabilityScannerTests(unittest.TestCase):
    def test_parse_game_ids_accepts_common_separators(self):
        self.assertEqual(
            parse_game_ids("2024021292,2024021291; 2024021290"),
            [2024021292, 2024021291, 2024021290],
        )

    def test_parse_game_ids_ignores_empty_parts(self):
        self.assertEqual(parse_game_ids("2024021292,,  ;2024021291"), [2024021292, 2024021291])

    def test_scanner_states_map_to_database_audit_states(self):
        self.assertEqual(SOURCE_STATUS_MAP["covered"], "available")
        self.assertEqual(SOURCE_STATUS_MAP["missing"], "missing_empty_response")
        self.assertEqual(SOURCE_STATUS_MAP["error"], "request_error")

    def test_explicit_ids_take_priority_over_range(self):
        class DbThatMustNotBeCalled:
            def query_to_df(self, *_args, **_kwargs):
                raise AssertionError("database should not be queried")

        self.assertEqual(select_games(DbThatMustNotBeCalled(), 50, [2, 1], 100, 200), [2, 1])

    def test_scan_games_checkpoints_complete_batches_and_remainder(self):
        original_fetch = scanner.fetch_shift_count
        batches = []
        scanner.fetch_shift_count = lambda game_id, _timeout: game_id
        try:
            rows = scan_games(
                [1, 2, 3],
                delay_seconds=0,
                timeout_seconds=1,
                batch_callback=lambda batch: batches.append(list(batch)),
                batch_size=2,
                progress_every=0,
            )
        finally:
            scanner.fetch_shift_count = original_fetch

        self.assertEqual(len(rows), 3)
        self.assertEqual([len(batch) for batch in batches], [2, 1])


if __name__ == "__main__":
    unittest.main()
