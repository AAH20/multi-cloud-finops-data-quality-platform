from __future__ import annotations

import argparse
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from .engine import ReliabilityEngine
from .loaders import load_billing, load_totals


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate multi-cloud billing data and financial close readiness")
    parser.add_argument("billing", help="normalized billing CSV")
    parser.add_argument("--invoices", required=True, help="provider invoice totals CSV")
    parser.add_argument("--ledger", required=True, help="general-ledger totals CSV")
    parser.add_argument("--as-of", required=True, type=date.fromisoformat)
    parser.add_argument("--freshness-days", type=int, default=2)
    parser.add_argument("--materiality", type=Decimal, default=Decimal("1"))
    parser.add_argument("--output", "-o")
    args = parser.parse_args()
    result = ReliabilityEngine(load_billing(args.billing), load_totals(args.invoices), load_totals(args.ledger),
                               as_of=args.as_of, freshness_days=args.freshness_days,
                               materiality=args.materiality).evaluate()
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()

