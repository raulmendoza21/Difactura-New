from __future__ import annotations

import re

from ..shared import looks_like_address_or_contact_line, looks_like_company_name, looks_like_tax_id_candidate
from .regions import FIELD_REGION_WEIGHTS


def base_region_score(field_name: str, region_name: str, logical_regions: dict[str, dict]) -> float:
    base_weight = FIELD_REGION_WEIGHTS.get(field_name, {}).get(region_name, 0.1)
    region_conf = float(logical_regions.get(region_name, {}).get("confidence", 0.35))
    region_count = len(logical_regions.get(region_name, {}).get("regions", []))
    return base_weight + region_conf * 0.9 + min(region_count, 3) * 0.05


def text_candidate_quality(field_name: str, value: str) -> float:
    score = min(len(value), 32) / 60
    if field_name == "fecha" and re.search(r"\d{4}-\d{2}-\d{2}|\d{2}[/-]\d{2}[/-]\d{4}", value):
        score += 0.8
    elif field_name in {"numero_factura", "rectified_invoice_number"}:
        if re.search(r"\d", value):
            score += 0.4
        if re.search(r"[A-Z]", value, re.IGNORECASE):
            score += 0.2
        if looks_like_tax_id_candidate(value):
            score -= 0.8
    return score


def party_candidate_quality(value: str) -> float:
    score = min(len(value), 48) / 80
    if looks_like_company_name(value):
        score += 0.8
    word_count = len(value.split())
    if word_count >= 2:
        score += 0.3
    elif word_count == 1:
        score -= 0.2
    if looks_like_address_or_contact_line(value):
        score -= 1.1
    return score


def amount_candidate_quality(field_name: str, value: float) -> float:
    score = 0.2
    magnitude = abs(value)
    score += min(magnitude, 1000.0) / 20000.0
    if field_name in {"iva_porcentaje", "retencion_porcentaje"} and 0 < magnitude <= 100:
        score += 0.9
    if field_name in {"total", "base_imponible", "iva", "retencion"} and magnitude >= 0.01:
        score += 0.25
    return score


def text_consensus_boost(value: str, values: list[tuple[str, str]]) -> float:
    normalized = _normalize_text_value(value)
    if not normalized:
        return 0.0
    matches = 0
    for _region_name, other_value in values:
        other_normalized = _normalize_text_value(other_value)
        if not other_normalized:
            continue
        if normalized == other_normalized:
            matches += 1
    return max(0, matches - 1) * 0.45


def amount_consensus_boost(value: float, values: list[tuple[str, float]]) -> float:
    matches = 0
    for _region_name, other_value in values:
        if abs(value - other_value) <= 0.02:
            matches += 1
    return max(0, matches - 1) * 0.45


def _normalize_text_value(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())
