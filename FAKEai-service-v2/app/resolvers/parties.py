"""Party extractor — find all entities (CIF + name) in the document.

NO role assignment (emisor/receptor). That decision is delegated to the AI layer.
This module just reports what it finds deterministically.
"""

from __future__ import annotations

from app.models.fields import ScanResult


def resolve(scan: ScanResult) -> dict:
    """Return {entities: [{cif, nombre, line_index}]} + confidence."""
    entities = []
    seen: set[str] = set()

    for hit in scan.tax_ids:
        if hit.tax_id not in seen:
            seen.add(hit.tax_id)
            entities.append({
                "cif": hit.tax_id,
                "nombre": hit.nearby_name or "",
                "line_index": hit.line_index,
            })

    return {
        "entities": entities,
        "confidence": {
            "entities": 0.9 if entities else 0.0,
        },
    }
