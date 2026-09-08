from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from typing import Any


def decimal(value: object) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.000001"))


@dataclass(frozen=True)
class BillingRow:
    row_id: str
    provider: str
    invoice_id: str
    charge_date: date
    resource_id: str
    service: str
    cost_center: str
    currency: str
    billed_cost: Decimal
    effective_cost: Decimal
    source_uri: str


@dataclass(frozen=True)
class ControlResult:
    control_id: str
    status: str
    severity: str
    message: str
    affected_amount: Decimal
    affected_rows: tuple[str, ...]
    evidence: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["affected_rows"] = list(self.affected_rows)
        result["evidence"] = list(self.evidence)
        result["affected_amount"] = str(self.affected_amount)
        return result

