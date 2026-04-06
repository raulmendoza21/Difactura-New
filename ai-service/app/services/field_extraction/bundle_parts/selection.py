from __future__ import annotations

from app.models.invoice_model import InvoiceData, LineItem

from ..shared import looks_like_address_or_contact_line, looks_like_tax_id_candidate
from .scoring import (
    amount_candidate_quality,
    amount_consensus_boost,
    base_region_score,
    party_candidate_quality,
    text_candidate_quality,
    text_consensus_boost,
)


def select_best_party_entity_candidates(
    region_candidates: dict[str, InvoiceData],
    logical_regions: dict[str, dict],
) -> dict[str, str]:
    provider_name, provider_tax_id = _select_best_entity("proveedor", "cif_proveedor", region_candidates, logical_regions)
    client_name, client_tax_id = _select_best_entity("cliente", "cif_cliente", region_candidates, logical_regions)
    return {
        "proveedor": provider_name,
        "cif_proveedor": provider_tax_id,
        "cliente": client_name,
        "cif_cliente": client_tax_id,
    }


def select_best_text_candidate(field_name: str, region_candidates: dict[str, InvoiceData], logical_regions: dict[str, dict]) -> str:
    scored: list[tuple[float, str]] = []
    values = [(region_name, str(getattr(candidate, field_name, "") or "").strip()) for region_name, candidate in region_candidates.items()]
    for region_name, value in values:
        if not value:
            continue
        score = base_region_score(field_name, region_name, logical_regions)
        score += text_candidate_quality(field_name, value)
        score += text_consensus_boost(value, values)
        scored.append((score, value))
    return max(scored, default=(0.0, ""), key=lambda item: item[0])[1]


def select_best_party_candidate(field_name: str, region_candidates: dict[str, InvoiceData], logical_regions: dict[str, dict]) -> str:
    scored: list[tuple[float, str]] = []
    values = [(region_name, str(getattr(candidate, field_name, "") or "").strip()) for region_name, candidate in region_candidates.items()]
    for region_name, value in values:
        if not value or looks_like_address_or_contact_line(value):
            continue
        score = base_region_score(field_name, region_name, logical_regions)
        score += party_candidate_quality(value)
        score += text_consensus_boost(value, values)
        scored.append((score, value))
    return max(scored, default=(0.0, ""), key=lambda item: item[0])[1]


def select_best_tax_id_candidate(field_name: str, region_candidates: dict[str, InvoiceData], logical_regions: dict[str, dict]) -> str:
    scored: list[tuple[float, str]] = []
    values = [(region_name, str(getattr(candidate, field_name, "") or "").strip()) for region_name, candidate in region_candidates.items()]
    for region_name, value in values:
        if not value:
            continue
        score = base_region_score(field_name, region_name, logical_regions)
        if looks_like_tax_id_candidate(value):
            score += 1.1
        score += text_consensus_boost(value, values)
        scored.append((score, value))
    return max(scored, default=(0.0, ""), key=lambda item: item[0])[1]


def select_best_amount_candidate(field_name: str, region_candidates: dict[str, InvoiceData], logical_regions: dict[str, dict]) -> float:
    scored: list[tuple[float, float]] = []
    values = [(region_name, float(getattr(candidate, field_name, 0.0) or 0.0)) for region_name, candidate in region_candidates.items()]
    for region_name, value in values:
        if abs(value) <= 0:
            continue
        score = base_region_score(field_name, region_name, logical_regions)
        score += amount_candidate_quality(field_name, value)
        score += amount_consensus_boost(value, values)
        scored.append((score, round(value, 2)))
    return max(scored, default=(0.0, 0.0), key=lambda item: item[0])[1]


def select_best_line_candidates(region_candidates: dict[str, InvoiceData], logical_regions: dict[str, dict]) -> list[LineItem]:
    scored: list[tuple[float, list[LineItem]]] = []
    for region_name, candidate in region_candidates.items():
        lines = list(getattr(candidate, "lineas", []) or [])
        if not lines:
            continue
        score = logical_regions.get(region_name, {}).get("confidence", 0.35)
        score += 1.0 if region_name == "line_items" else 0.45 if region_name == "full" else 0.25
        score += min(len(lines), 10) / 100
        scored.append((score, lines))
    return max(scored, default=(0.0, []), key=lambda item: item[0])[1]


def _select_best_entity(
    name_field: str,
    tax_field: str,
    region_candidates: dict[str, InvoiceData],
    logical_regions: dict[str, dict],
) -> tuple[str, str]:
    scored: list[tuple[float, str, str]] = []
    for region_name, candidate in region_candidates.items():
        name_value = str(getattr(candidate, name_field, "") or "").strip()
        tax_value = str(getattr(candidate, tax_field, "") or "").strip()
        if not name_value and not tax_value:
            continue
        if name_value and looks_like_address_or_contact_line(name_value):
            continue

        score = base_region_score(name_field, region_name, logical_regions)
        if name_value:
            score += party_candidate_quality(name_value)
        if tax_value and looks_like_tax_id_candidate(tax_value):
            score += 1.1

        pair_values = [
            (
                str(getattr(other_candidate, name_field, "") or "").strip(),
                str(getattr(other_candidate, tax_field, "") or "").strip(),
            )
            for other_candidate in region_candidates.values()
        ]
        score += _entity_consensus_boost(name_value, tax_value, pair_values)
        scored.append((score, name_value, tax_value))

    if not scored:
        return "", ""
    _score, name_value, tax_value = max(scored, key=lambda item: item[0])
    return name_value, tax_value


def _entity_consensus_boost(name_value: str, tax_value: str, values: list[tuple[str, str]]) -> float:
    matches = 0
    normalized_name = "".join(char for char in name_value.upper() if char.isalnum())
    normalized_tax_id = "".join(char for char in tax_value.upper() if char.isalnum())
    for other_name, other_tax_id in values:
        other_normalized_name = "".join(char for char in other_name.upper() if char.isalnum())
        other_normalized_tax = "".join(char for char in other_tax_id.upper() if char.isalnum())
        if normalized_tax_id and other_normalized_tax and normalized_tax_id == other_normalized_tax:
            matches += 1
            continue
        if normalized_name and other_normalized_name and normalized_name == other_normalized_name:
            matches += 1
    return max(0, matches - 1) * 0.45
