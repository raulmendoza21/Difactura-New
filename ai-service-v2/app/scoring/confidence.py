"""Confidence scorer — aggregate per-field confidences into overall score."""

from __future__ import annotations


# Weights define how much each field matters for the overall confidence.
# Role fields (proveedor/cliente) have lower weight since they depend on AI.
FIELD_WEIGHTS: dict[str, float] = {
    "numero_factura": 0.12,
    "fecha": 0.12,
    "entities": 0.15,
    "base_imponible": 0.18,
    "iva_porcentaje": 0.05,
    "iva": 0.10,
    "total": 0.18,
    "proveedor": 0.03,
    "cif_proveedor": 0.03,
    "cliente": 0.02,
    "cif_cliente": 0.02,
}


def compute_overall(field_confidences: dict[str, float]) -> float:
    """Weighted average of per-field confidences → overall 0..1 score."""
    total_weight = 0.0
    weighted_sum = 0.0

    for field, weight in FIELD_WEIGHTS.items():
        conf = field_confidences.get(field, 0.0)
        weighted_sum += conf * weight
        total_weight += weight

    if total_weight == 0:
        return 0.0

    return round(weighted_sum / total_weight, 2)


def merge_confidences(*dicts: dict) -> dict[str, float]:
    """Merge multiple confidence dicts into one flat dict."""
    merged: dict[str, float] = {}
    for d in dicts:
        for k, v in d.items():
            if isinstance(v, (int, float)):
                merged[k] = v
    return merged
