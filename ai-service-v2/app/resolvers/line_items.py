"""Line items resolver — extract table rows and map to LineItem."""

from __future__ import annotations

from app.discovery.table_scanner import scan_table
from app.models.fields import ScanResult, TableRow
from app.models.invoice import LineItem
from app.utils.math_ops import approx_eq, round2


def resolve(scan: ScanResult, base_imponible: float | None = None) -> dict:
    """Return {lineas: list[LineItem]} + confidence."""
    rows = scan_table(scan.lines)

    if not rows:
        return {"lineas": [], "confidence": {"lineas": 0.0}}

    items = [_row_to_item(r) for r in rows]

    # Validate: sum of line amounts ≈ base_imponible
    conf = _compute_confidence(items, base_imponible)

    return {"lineas": items, "confidence": {"lineas": conf}}


def _row_to_item(row: TableRow) -> LineItem:
    return LineItem(
        descripcion=row.description,
        cantidad=row.quantity,
        precio_unitario=row.unit_price,
        importe=row.amount,
    )


def _compute_confidence(items: list[LineItem], base: float | None) -> float:
    if not items:
        return 0.0

    # Base confidence from having any rows
    conf = 0.5

    # Bonus if all items have an amount
    all_amounts = all(i.importe is not None for i in items)
    if all_amounts:
        conf += 0.1

    # Bonus if line sum matches base_imponible
    if base is not None and all_amounts:
        total_lines = round2(sum(i.importe for i in items if i.importe))
        if approx_eq(total_lines, base, tol=0.10):
            conf += 0.35
        elif approx_eq(total_lines, base, tol=1.0):
            conf += 0.15

    # Bonus if qty × price ≈ amount for most items
    valid_math = 0
    for item in items:
        if item.cantidad and item.precio_unitario and item.importe:
            expected = round2(item.cantidad * item.precio_unitario)
            if approx_eq(expected, item.importe, tol=0.02):
                valid_math += 1
    if items and valid_math == len(items):
        conf += 0.1

    return min(conf, 0.95)
