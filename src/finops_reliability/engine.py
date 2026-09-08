from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal

from .models import BillingRow, ControlResult, decimal


class ReliabilityEngine:
    """Runs deterministic close-readiness controls over normalized billing rows."""

    def __init__(self, rows: list[BillingRow], invoices: dict[str, Decimal], ledger: dict[str, Decimal],
                 *, as_of: date, freshness_days: int = 2, materiality: Decimal = Decimal("1")):
        self.rows = rows
        self.invoices = invoices
        self.ledger = ledger
        self.as_of = as_of
        self.freshness_days = freshness_days
        self.materiality = materiality

    def evaluate(self) -> dict[str, object]:
        controls = [self._freshness(), self._duplicates(), self._dimensions(), self._currencies(),
                    self._reconcile("FIN-REC-001", "invoice", self.invoices),
                    self._reconcile("FIN-GL-001", "general-ledger", self.ledger)]
        blockers = [c for c in controls if c.status == "fail" and c.severity == "blocking"]
        total = sum((row.billed_cost for row in self.rows), Decimal())
        allocated = sum((row.billed_cost for row in self.rows
                         if row.cost_center not in ("", "unallocated")), Decimal())
        payload: dict[str, object] = {
            "schema_version": "1.0",
            "as_of": self.as_of.isoformat(),
            "close_ready": not blockers,
            "close_readiness_score": max(0, 100 - 25 * len(blockers)
                                             - 5 * sum(c.status == "warn" for c in controls)),
            "billed_total": str(decimal(total)),
            "allocation_coverage_percent": str(decimal(allocated / total * 100)) if total else "0.000000",
            "controls": [control.as_dict() for control in controls],
            "impact_lineage": self._lineage(controls),
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        payload["evidence_sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
        return payload

    def _freshness(self) -> ControlResult:
        if not self.rows:
            return self._result("FIN-FRESH-001", "fail", "blocking", "No billing rows received.")
        latest = max(row.charge_date for row in self.rows)
        age = (self.as_of - latest).days
        return self._result("FIN-FRESH-001", "pass" if age <= self.freshness_days else "fail", "blocking",
                            f"Latest charge is {age} day(s) old; limit is {self.freshness_days}.",
                            evidence=(f"latest_charge_date={latest}", f"as_of={self.as_of}"))

    def _duplicates(self) -> ControlResult:
        counts = Counter(row.row_id for row in self.rows)
        identifiers = tuple(sorted(key for key, count in counts.items() if count > 1))
        affected = sum((row.billed_cost for row in self.rows if row.row_id in identifiers), Decimal())
        return self._result("FIN-UNIQ-001", "fail" if identifiers else "pass", "blocking",
                            f"Found {len(identifiers)} duplicated row identifier(s).", affected, identifiers)

    def _dimensions(self) -> ControlResult:
        missing = tuple(row.row_id for row in self.rows
                        if not row.resource_id or not row.service or not row.source_uri)
        if missing:
            return self._result("FIN-DIM-001", "fail", "blocking", "Required lineage dimensions are missing.",
                                affected_rows=missing)
        unallocated = tuple(row.row_id for row in self.rows if row.cost_center in ("", "unallocated"))
        affected = sum((row.billed_cost for row in self.rows if row.row_id in unallocated), Decimal())
        return self._result("FIN-DIM-001", "warn" if unallocated else "pass", "warning",
                            f"{len(unallocated)} row(s) lack cost-center allocation.", affected, unallocated)

    def _currencies(self) -> ControlResult:
        values = tuple(sorted({row.currency for row in self.rows}))
        return self._result("FIN-CUR-001", "pass" if len(values) <= 1 else "fail", "blocking",
                            f"Observed currencies: {', '.join(values) or 'none'}.", evidence=values)

    def _reconcile(self, control_id: str, label: str, expected: dict[str, Decimal]) -> ControlResult:
        actual: dict[str, Decimal] = defaultdict(Decimal)
        for row in self.rows:
            actual[row.invoice_id] += row.billed_cost
        evidence: list[str] = []
        affected = Decimal()
        for invoice_id in sorted(set(actual) | set(expected)):
            delta = decimal(actual.get(invoice_id, Decimal()) - expected.get(invoice_id, Decimal()))
            if abs(delta) > self.materiality:
                evidence.append(f"{invoice_id}={delta}")
                affected += abs(delta)
        return self._result(control_id, "fail" if evidence else "pass", "blocking",
                            f"{len(evidence)} {label} variance(s) exceed materiality {self.materiality}.",
                            affected, evidence=tuple(evidence))

    def _lineage(self, controls: list[ControlResult]) -> dict[str, list[str]]:
        mapping = {
            "FIN-FRESH-001": ["forecast", "anomaly_detection", "month_close"],
            "FIN-UNIQ-001": ["invoice_reconciliation", "chargeback", "unit_economics"],
            "FIN-DIM-001": ["chargeback", "product_margin", "customer_showback"],
            "FIN-CUR-001": ["forecast", "executive_dashboard", "month_close"],
            "FIN-REC-001": ["provider_payment", "savings_verification", "month_close"],
            "FIN-GL-001": ["financial_statements", "budget_variance", "month_close"],
        }
        return {control.control_id: mapping[control.control_id] for control in controls if control.status != "pass"}

    @staticmethod
    def _result(control_id: str, status: str, severity: str, message: str,
                affected: Decimal = Decimal(), affected_rows: tuple[str, ...] = (),
                evidence: tuple[str, ...] = ()) -> ControlResult:
        return ControlResult(control_id, status, severity, message, decimal(affected), affected_rows, evidence)
