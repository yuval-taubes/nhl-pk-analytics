"""Static regression checks for the conservative shift-source migration."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class ShiftSourceMigrationTests(unittest.TestCase):
    def test_migration_does_not_infer_missing_from_absent_rows(self):
        source = (ROOT / "Analytics" / "diagnostics" / "migrate_shift_source_status.py").read_text(encoding="utf-8")
        self.assertIn("THEN 'available' ELSE 'not_checked'", source)
        self.assertNotIn("THEN 'available' ELSE 'missing_empty_response'", source)

    def test_audit_only_is_read_only_and_skips_schema_execution(self):
        source = (ROOT / "Analytics" / "diagnostics" / "migrate_shift_source_status.py").read_text(encoding="utf-8")
        self.assertIn('"--audit-only"', source)
        self.assertIn('cursor.execute("SET TRANSACTION READ ONLY")', source)
        self.assertIn("if args.audit_only:", source)
        self.assertIn("else:\n                cursor.execute(SCHEMA_PATH.read_text", source)

    def test_schema_has_explicit_source_states(self):
        schema = (ROOT / "NhlPkIngest" / "schema.sql").read_text(encoding="utf-8")
        for status in ("available", "missing_empty_response", "request_error", "not_checked"):
            self.assertIn(status, schema)


if __name__ == "__main__":
    unittest.main()
