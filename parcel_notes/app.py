"""Print aggregate shipment counts without displaying shipment details."""

import json
from pathlib import Path
import sys


DEFAULT_DATA = Path(__file__).resolve().parents[1] / "data" / "parcels.json"


def load_parcels(path):
    try:
        rows = json.loads(Path(path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ValueError("Invalid parcel data") from exc
    if not isinstance(rows, list) or any(
        not isinstance(row, dict)
        or not isinstance(row.get("id"), str)
        or not row["id"].strip()
        or row.get("status") not in ("delivered", "in_transit")
        for row in rows
    ):
        raise ValueError("Invalid parcel data")
    return rows


def summarize(parcels):
    delivered = sum(row["status"] == "delivered" for row in parcels)
    return {"total": len(parcels), "delivered": delivered,
            "in_transit": len(parcels) - delivered}


def main(path=DEFAULT_DATA, *, out=None, err=None):
    out = sys.stdout if out is None else out
    err = sys.stderr if err is None else err
    try:
        counts = summarize(load_parcels(path))
    except (OSError, ValueError):
        print("Unable to read parcel data.", file=err)
        return 1
    print("Parcel Notes", file=out)
    print(f"Shipments: {counts['total']}", file=out)
    print(f"Delivered: {counts['delivered']}", file=out)
    print(f"In transit: {counts['in_transit']}", file=out)
    return 0
