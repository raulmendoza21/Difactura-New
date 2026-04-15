"""Amount resolver — base, tax rate, tax amount, total, withholdings.

Core innovation: try ALL numeric combinations and score them mathematically.
The combination with the best math consistency wins.
"""

from __future__ import annotations

import re
from itertools import combinations

from app.models.fields import NumericCandidate, ScanResult
from app.utils.math_ops import approx_eq, infer_missing, round2, try_tax_combination
from app.utils.regex_lib import (
    ALL_TAX_RATES,
    IGIC_RATES,
    IVA_RATES,
    LABEL_BASE,
    LABEL_TAX,
    LABEL_TOTAL,
    LABEL_WITHHOLDING,
    PERCENT,
)
from app.utils.text import normalize_keyword


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def resolve(scan: ScanResult) -> dict:
    """Return {base_imponible, iva_porcentaje, iva, retencion_porcentaje, retencion, total}."""
    amounts = scan.amounts

    if not amounts:
        return _empty() | {"confidence": _zero_conf()}

    # Step 1: label-based assignment
    labeled = _assign_by_labels(amounts)

    # Step 2: try to find tax rate from percentages in text
    rates = _find_tax_rates(scan)

    # Step 3: mathematical brute-force — try all combos and pick best score
    best = _math_solve(amounts, rates, labeled)

    # Step 4: withholdings
    ret = _resolve_withholdings(amounts, scan)

    result = {
        "base_imponible": best.get("base"),
        "iva_porcentaje": best.get("rate"),
        "iva": best.get("tax"),
        "total": best.get("total"),
        "retencion_porcentaje": ret.get("rate"),
        "retencion": ret.get("amount"),
    }

    # Step 5: infer missing if possible
    result = _try_infer(result)

    conf = _score_confidence(result, best.get("math_score", 0.0))
    result["confidence"] = conf
    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _assign_by_labels(amounts: list[NumericCandidate]) -> dict:
    """Heuristic: assign amounts to roles based on their label context."""
    assigned: dict[str, float | None] = {"base": None, "tax": None, "total": None}

    for a in amounts:
        lbl = normalize_keyword(a.label).lower() if a.label else ""
        if LABEL_BASE.search(lbl):
            assigned["base"] = a.value
        elif LABEL_TAX.search(lbl):
            assigned["tax"] = a.value
        elif LABEL_TOTAL.search(lbl):
            assigned["total"] = a.value

    return assigned


def _find_tax_rates(scan: ScanResult) -> list[float]:
    """Extract explicit tax percentages from text."""
    rates: list[float] = []
    for m in PERCENT.finditer(scan.raw_text):
        value = float(m.group(1).replace(",", "."))
        if value in ALL_TAX_RATES:
            rates.append(value)

    # Deduplicate keeping order
    seen: set[float] = set()
    unique: list[float] = []
    for r in rates:
        if r not in seen:
            seen.add(r)
            unique.append(r)
    return unique


def _math_solve(
    amounts: list[NumericCandidate],
    rates: list[float],
    labeled: dict,
) -> dict:
    """Try combinations of amounts and rate to find best math-consistent set."""
    values = [a.value for a in amounts if a.value > 0]

    # If there are labeled values, prefer them as starting point
    if labeled["base"] and labeled["total"]:
        result = _try_labeled_combo(labeled, rates, values)
        if result["math_score"] > 0.7:
            return result

    # Start with rates found in document, plus standard rates as fallback
    candidate_rates = list(rates) if rates else list(ALL_TAX_RATES)

    best: dict = {"base": None, "rate": None, "tax": None, "total": None, "math_score": 0.0}

    # Unique positive values sorted descending
    unique_vals = sorted(set(values), reverse=True)

    # Try pairs of amounts
    for i, v1 in enumerate(unique_vals):
        for v2 in unique_vals[i + 1:]:
            for rate in candidate_rates:
                # v1 = total, v2 = base
                score = try_tax_combination(base=v2, rate=rate, tax=None, total=v1)
                if score > best["math_score"]:
                    tax = round2(v1 - v2)
                    best = {"base": v2, "rate": rate, "tax": tax, "total": v1, "math_score": score}

                # v1 = base, v2 = tax
                total = round2(v1 + v2)
                score = try_tax_combination(base=v1, rate=rate, tax=v2, total=total)
                if score > best["math_score"]:
                    best = {"base": v1, "rate": rate, "tax": v2, "total": total, "math_score": score}

    # Try triplets: base, tax, total
    if len(unique_vals) >= 3:
        for v_total, v_base, v_tax in combinations(unique_vals, 3):
            if not approx_eq(v_base + v_tax, v_total, tol=0.05):
                continue
            for rate in candidate_rates:
                score = try_tax_combination(base=v_base, rate=rate, tax=v_tax, total=v_total)
                if score > best["math_score"]:
                    best = {"base": v_base, "rate": rate, "tax": v_tax, "total": v_total, "math_score": score}

    # If math couldn't solve it, fall back to labeled values
    if best["math_score"] < 0.3 and (labeled["base"] or labeled["total"]):
        return _try_labeled_combo(labeled, candidate_rates, unique_vals) | {"math_score": 0.3}

    # If still nothing, take the largest value as total
    if best["math_score"] < 0.1 and unique_vals:
        best = {"base": None, "rate": None, "tax": None, "total": unique_vals[0], "math_score": 0.1}

    return best


def _try_labeled_combo(labeled: dict, rates: list[float], values: list[float]) -> dict:
    """Build best result from labeled amounts."""
    base = labeled.get("base")
    total = labeled.get("total")
    tax = labeled.get("tax")

    best_score = 0.0
    best: dict = {"base": base, "rate": None, "tax": tax, "total": total, "math_score": 0.0}

    candidate_rates = rates if rates else list(ALL_TAX_RATES)
    for rate in candidate_rates:
        score = try_tax_combination(base=base, rate=rate, tax=tax, total=total)
        if score > best_score:
            best_score = score
            best = {"base": base, "rate": rate, "tax": tax, "total": total, "math_score": score}

    # Try to fill in missing from math
    if base and total and not tax:
        best["tax"] = round2(total - base)
    elif base and tax and not total:
        best["total"] = round2(base + tax)
    elif total and tax and not base:
        best["base"] = round2(total - tax)

    return best


def _resolve_withholdings(amounts: list[NumericCandidate], scan: ScanResult) -> dict:
    """Extract withholding (retención) if present."""
    for a in amounts:
        lbl = normalize_keyword(a.label).lower() if a.label else ""
        if LABEL_WITHHOLDING.search(lbl):
            # Look for the percentage nearby
            rate = _find_withholding_rate(scan, a.line_index)
            return {"rate": rate, "amount": a.value}

    # Search for withholding in text directly
    pattern = re.compile(
        r"retenci[oó]n.*?(\d{1,2}(?:[.,]\d+)?)\s*%.*?(\d+[.,]\d{2})",
        re.IGNORECASE,
    )
    m = pattern.search(scan.raw_text)
    if m:
        rate = float(m.group(1).replace(",", "."))
        amount = float(m.group(2).replace(",", "."))
        return {"rate": rate, "amount": amount}

    return {"rate": None, "amount": None}


def _find_withholding_rate(scan: ScanResult, near_line: int) -> float | None:
    """Find withholding percentage near the withholding amount."""
    search_start = max(0, near_line - 2)
    search_end = min(len(scan.lines), near_line + 3)
    for i in range(search_start, search_end):
        m = PERCENT.search(scan.lines[i])
        if m:
            v = float(m.group(1).replace(",", "."))
            if v in (7, 15, 19, 21):
                return v
    return None


def _try_infer(result: dict) -> dict:
    """Fill missing values using math relationships."""
    filled = infer_missing(
        base=result.get("base_imponible"),
        rate=result.get("iva_porcentaje"),
        tax=result.get("iva"),
        total=result.get("total"),
    )
    if filled["base"] is not None:
        result["base_imponible"] = filled["base"]
    if filled["rate"] is not None:
        result["iva_porcentaje"] = filled["rate"]
    if filled["tax"] is not None:
        result["iva"] = filled["tax"]
    if filled["total"] is not None:
        result["total"] = filled["total"]
    return result


def _score_confidence(result: dict, math_score: float) -> dict:
    """Assign per-field confidence for amount fields."""
    conf: dict[str, float] = {}

    for field in ("base_imponible", "iva_porcentaje", "iva", "total"):
        if result.get(field) is not None:
            # Math-validated fields get a boost
            conf[field] = min(0.98, 0.5 + math_score * 0.5)
        else:
            conf[field] = 0.0

    for field in ("retencion_porcentaje", "retencion"):
        conf[field] = 0.8 if result.get(field) is not None else 0.0

    return conf


def _empty() -> dict:
    return {
        "base_imponible": None,
        "iva_porcentaje": None,
        "iva": None,
        "total": None,
        "retencion_porcentaje": None,
        "retencion": None,
    }


def _zero_conf() -> dict:
    return {k: 0.0 for k in (
        "base_imponible", "iva_porcentaje", "iva", "total",
        "retencion_porcentaje", "retencion",
    )}
