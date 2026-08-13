"""Canonical identity resolution with explicit unresolved and ambiguous outcomes."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class IdentityResolution:
    status: str
    canonical_wafer: str | None
    canonical_lot: str | None
    canonical_work_order: str | None
    product_code: str | None
    method: str
    source_identity: str


class IdentityResolver:
    def __init__(self, alias_rows: list[dict[str, object]]) -> None:
        candidates: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
        for row in alias_rows:
            candidates[(str(row["alias_type"]), str(row["alias_value"]))].append(row)
        self._candidates = candidates

    def resolve(self, alias_type: str, alias_value: str | None) -> IdentityResolution:
        identity = alias_value or "<missing>"
        matches = self._candidates.get((alias_type, identity), [])
        if not matches:
            return IdentityResolution("UNRESOLVED", None, None, None, None, alias_type, identity)
        unique_wafers = {str(row["canonical_wafer"]) for row in matches}
        if len(unique_wafers) != 1:
            return IdentityResolution("AMBIGUOUS", None, None, None, None, alias_type, identity)
        match = matches[0]
        return IdentityResolution(
            "RESOLVED",
            str(match["canonical_wafer"]),
            str(match["canonical_lot"]),
            str(match["canonical_work_order"]),
            str(match["product_code"]),
            alias_type,
            identity,
        )

    def resolve_mes(self, row: dict[str, object]) -> IdentityResolution:
        if row.get("substrate_serial"):
            resolved = self.resolve("SUBSTRATE_SERIAL", str(row["substrate_serial"]))
            if resolved.status == "RESOLVED":
                return resolved
        return self.resolve("LOT_WAFER", f"{row['lot_ref']}|{row['wafer_number']}")

    def resolve_inspection(self, row: dict[str, object]) -> IdentityResolution:
        return self.resolve("INSPECTION_ALIAS", str(row.get("substrate_ref") or ""))

    def resolve_chip(self, row: dict[str, object]) -> IdentityResolution:
        return self.resolve("SUBSTRATE_SERIAL", str(row.get("wafer_alias") or ""))

    def resolve_sorting(self, row: dict[str, object]) -> IdentityResolution:
        return self.resolve("ORDER_WAFER", f"{row['order_number']}|{row['wafer_sequence']}")

    def resolve_qualification(self, row: dict[str, object]) -> IdentityResolution:
        return self.resolve("LOT_WAFER", f"{row['lot_number']}|{row['wafer_sequence']}")
