"""Financial math helpers — tolerance comparisons, rounding."""

from __future__ import annotations


def approx_eq(a: float, b: float, tol: float = 0.05) -> bool:
    return abs(a - b) <= tol


def round2(value: float) -> float:
    return round(value, 2)


def try_tax_combination(
    base: float | None, rate: float | None, tax: float | None, total: float | None,
    *, withholding: float | None = 0.0,
) -> float:
    """Return quality score (0-1) for a (base, rate, tax, total) combination.

    A perfect score means everything checks out mathematically.
    """
    base = base or 0.0
    rate = rate or 0.0
    tax = tax or 0.0
    total = total or 0.0
    withholding = withholding or 0.0

    if base <= 0 and total <= 0:
        return 0.0

    score = 0.0
    expected_tax = round2(abs(base) * rate / 100) if rate else 0.0

    # Check base × rate ≈ tax
    if tax and expected_tax and approx_eq(expected_tax, abs(tax), max(0.10, abs(expected_tax) * 0.02)):
        score += 0.5
    elif not tax and not expected_tax:
        score += 0.3

    # Check base + tax - withholding ≈ total
    expected_total = round2(abs(base) + abs(tax) - abs(withholding))
    if total and approx_eq(expected_total, abs(total), max(0.10, abs(total) * 0.02)):
        score += 0.5
    elif not total:
        score += 0.1

    return min(score, 1.0)


def infer_missing(
    base: float | None, rate: float | None, tax: float | None, total: float | None,
    *, withholding: float | None = 0.0,
) -> dict[str, float | None]:
    """Fill in missing values using the ones we have."""
    base = base or 0.0
    rate = rate or 0.0
    tax = tax or 0.0
    total = total or 0.0
    withholding = withholding or 0.0
    result: dict[str, float | None] = {"base": base, "rate": rate, "tax": tax, "total": total, "withholding": withholding}

    if not tax and base and rate:
        result["tax"] = round2(base * rate / 100)
    if not total and (base or result["tax"]):
        result["total"] = round2((base or 0.0) + (result["tax"] or 0.0) - withholding)
    if not base and total and result["tax"]:
        result["base"] = round2(total - (result["tax"] or 0.0) + withholding)
    if not rate and base and result["tax"] and abs(base) > 0.01:
        result["rate"] = round2(abs(result["tax"] or 0.0) / abs(base) * 100)

    return result
