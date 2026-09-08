from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

from .models import BillingRow, decimal

REQUIRED = {"row_id", "provider", "invoice_id", "charge_date", "resource_id", "service",
            "cost_center", "currency", "billed_cost", "effective_cost", "source_uri"}


def load_billing(path: str | Path) -> list[BillingRow]:
    with Path(path).open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        missing = REQUIRED - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"missing required columns: {', '.join(sorted(missing))}")
        return [BillingRow(
            row_id=row["row_id"], provider=row["provider"].lower(), invoice_id=row["invoice_id"],
            charge_date=date.fromisoformat(row["charge_date"][:10]), resource_id=row["resource_id"],
            service=row["service"], cost_center=row["cost_center"], currency=row["currency"],
            billed_cost=decimal(row["billed_cost"]), effective_cost=decimal(row["effective_cost"]),
            source_uri=row["source_uri"],
        ) for row in reader]


def load_totals(path: str | Path) -> dict[str, Decimal]:
    with Path(path).open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if not {"invoice_id", "amount"}.issubset(reader.fieldnames or ()):
            raise ValueError("totals file requires invoice_id and amount")
        return {row["invoice_id"]: decimal(row["amount"]) for row in reader}
