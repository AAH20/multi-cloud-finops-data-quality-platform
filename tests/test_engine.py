from datetime import date
from decimal import Decimal
from pathlib import Path
import unittest

from finops_reliability.engine import ReliabilityEngine
from finops_reliability.loaders import load_billing, load_totals

ROOT = Path(__file__).parents[1]


class ReliabilityTests(unittest.TestCase):
    def run_fixture(self, quality: str):
        return ReliabilityEngine(
            load_billing(ROOT / f"fixtures/billing-{quality}.csv"),
            load_totals(ROOT / f"fixtures/invoices-{quality}.csv"),
            load_totals(ROOT / f"fixtures/ledger-{quality}.csv"),
            as_of=date(2026, 9, 8), materiality=Decimal("1"),
        ).evaluate()

    def test_bad_close_fails_with_lineage(self):
        report = self.run_fixture("bad")
        self.assertFalse(report["close_ready"])
        self.assertEqual(report["close_readiness_score"], 0)
        self.assertIn("FIN-UNIQ-001", report["impact_lineage"])
        self.assertEqual(len(report["evidence_sha256"]), 64)

    def test_clean_close_passes(self):
        report = self.run_fixture("good")
        self.assertTrue(report["close_ready"])
        self.assertEqual(report["close_readiness_score"], 100)
        self.assertEqual(report["allocation_coverage_percent"], "100.000000")
        self.assertEqual(report["impact_lineage"], {})

    def test_evidence_is_deterministic(self):
        self.assertEqual(self.run_fixture("good")["evidence_sha256"],
                         self.run_fixture("good")["evidence_sha256"])

    def test_missing_schema_fails_early(self):
        with self.assertRaisesRegex(ValueError, "missing required columns"):
            load_billing(ROOT / "fixtures/invoices-good.csv")


if __name__ == "__main__":
    unittest.main()

