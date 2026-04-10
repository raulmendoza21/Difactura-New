"""Pipeline orchestrator — linear flow: load → discover → resolve → AI assign → result.

Deterministic layer extracts what's reliable: CIFs, names, amounts, dates, line items.
AI layer handles decisions: emisor/receptor assignment, compra/venta.
"""

from __future__ import annotations

import logging
import time

from app.ai_fallback.field_filler import fill_weak_fields
from app.config import Settings
from app.discovery.field_scanner import scan
from app.loading.loader import load_document
from app.models.invoice import Entity, InvoiceData
from app.models.result import ExtractionResult
from app.resolvers import amounts as amount_resolver
from app.resolvers import identity as identity_resolver
from app.resolvers import line_items as line_items_resolver
from app.resolvers import operation as operation_resolver
from app.resolvers import parties as party_resolver
from app.scoring.confidence import compute_overall, merge_confidences

logger = logging.getLogger(__name__)


async def extract(
    file_path: str,
    mime_type: str,
    company_name: str | None = None,
    company_tax_id: str | None = None,
    company_tax_ids: list[str] | None = None,
    settings: Settings | None = None,
) -> ExtractionResult:
    """Main extraction pipeline. Returns ExtractionResult."""
    settings = settings or Settings()
    t0 = time.time()
    warnings: list[str] = []

    # 1. Load document → raw text + pages
    doc = load_document(file_path, mime_type)
    raw_text = doc["text"]
    pages = doc["pages"]
    source = doc["source"]

    if not raw_text.strip():
        warnings.append("Empty document — no text extracted")
        return _empty_result(raw_text, source, pages, warnings)

    # 2. Discover — scan all structured data
    scan_result = scan(raw_text)

    # 3. Resolve identity (invoice number + date)
    identity = identity_resolver.resolve(scan_result)

    # 4. Extract entities (CIFs + names — no role assignment)
    parties = party_resolver.resolve(scan_result)
    entities = [Entity(cif=e["cif"], nombre=e["nombre"]) for e in parties["entities"]]

    # 5. Resolve amounts (base, tax, total, withholdings)
    money = amount_resolver.resolve(scan_result)

    # 6. Resolve line items
    lines = line_items_resolver.resolve(scan_result, money.get("base_imponible"))

    # 7. Resolve operation type + tax regime (no side)
    ops = operation_resolver.resolve(scan_result, iva_porcentaje=money.get("iva_porcentaje"))

    # 8. Build InvoiceData — entities populated, roles assigned by position
    #    First entity in OCR text = emisor (proveedor), second = receptor (cliente)
    company_ids = {c.upper().strip() for c in (company_tax_ids or []) if c}
    prov_name, prov_cif, cli_name, cli_cif = "", "", "", ""
    role_conf = 0.0

    if len(entities) >= 2:
        prov_cif = entities[0].cif
        prov_name = entities[0].nombre
        cli_cif = entities[1].cif
        cli_name = entities[1].nombre
        role_conf = 0.8
    elif len(entities) == 1:
        e = entities[0]
        if e.cif.upper().strip() in company_ids:
            # Our company is the only entity → we emit
            prov_cif = e.cif
            prov_name = e.nombre
        else:
            # External company is the only entity → they emit to us
            prov_cif = e.cif
            prov_name = e.nombre
        role_conf = 0.5  # low — only 1 entity, less certain

    data = InvoiceData(
        numero_factura=identity["numero_factura"] or "",
        rectified_invoice_number=identity["rectified_invoice_number"] or "",
        fecha=identity["fecha"] or "",
        tipo_factura=ops["tipo_factura"],
        entities=entities,
        proveedor=prov_name,
        cif_proveedor=prov_cif,
        cliente=cli_name,
        cif_cliente=cli_cif,
        base_imponible=money.get("base_imponible") or 0,
        iva_porcentaje=money.get("iva_porcentaje") or 0,
        iva=money.get("iva") or 0,
        retencion_porcentaje=money.get("retencion_porcentaje") or 0,
        retencion=money.get("retencion") or 0,
        total=money.get("total") or 0,
        tax_regime=ops["tax_regime"],
        lineas=lines.get("lineas", []),
    )

    # 9. Merge per-field confidences
    field_conf = merge_confidences(
        identity.get("confidence", {}),
        parties.get("confidence", {}),
        money.get("confidence", {}),
        lines.get("confidence", {}),
        ops.get("confidence", {}),
    )
    # Role fields get confidence from position-based assignment
    field_conf["proveedor"] = role_conf if prov_name else 0.0
    field_conf["cif_proveedor"] = role_conf if prov_cif else 0.0
    field_conf["cliente"] = role_conf if cli_name else 0.0
    field_conf["cif_cliente"] = role_conf if cli_cif else 0.0
    field_conf["operation_side"] = 0.0

    # 10. AI layer — assign roles + fill weak fields
    company_ctx = None
    if company_name or company_tax_id or company_tax_ids:
        company_ctx = {
            "name": company_name or "",
            "tax_id": company_tax_id or "",
            "tax_ids": company_tax_ids or [],
        }

    data_dict = data.model_dump()
    ai_filled = await fill_weak_fields(
        raw_text, data_dict, field_conf, settings, company_context=company_ctx,
    )
    if ai_filled:
        for k, v in ai_filled.items():
            if hasattr(data, k):
                setattr(data, k, v)
                field_conf[k] = max(field_conf.get(k, 0), 0.7)
        source = f"{source}+ai"
        warnings.append(f"AI filled: {', '.join(ai_filled.keys())}")

    # 10b. Deterministic operation_side from assigned roles
    data.operation_side = _resolve_side(
        data.cif_proveedor, data.cif_cliente, company_tax_ids or []
    )
    if data.operation_side:
        field_conf["operation_side"] = 0.95

    # 11. Compute overall confidence
    overall = compute_overall(field_conf)
    data.confianza = overall

    elapsed = round(time.time() - t0, 3)
    logger.info("Extraction completed in %.3fs — confidence=%.2f", elapsed, overall)

    return ExtractionResult(
        data=data,
        field_confidence=field_conf,
        document_type=ops["tipo_factura"],
        tax_regime=ops["tax_regime"],
        operation_side=data.operation_side,
        raw_text=raw_text,
        method="heuristic" if "ai" not in source else "heuristic+ai",
        provider=source,
        pages=pages,
        warnings=warnings,
    )


def _resolve_side(
    cif_proveedor: str, cif_cliente: str, company_tax_ids: list[str],
) -> str:
    """Determine operation_side deterministically from assigned CIFs."""
    if not company_tax_ids:
        return ""
    ids = {c.upper().strip() for c in company_tax_ids if c}
    prov = (cif_proveedor or "").upper().strip()
    cli = (cif_cliente or "").upper().strip()
    if prov in ids:
        return "venta"
    if cli in ids:
        return "compra"
    # Our company not found in either role — assume we received the invoice
    if cif_proveedor:
        return "compra"
    return ""


def _empty_result(raw: str, source: str, pages: int, warnings: list[str]) -> ExtractionResult:
    return ExtractionResult(
        data=InvoiceData(),
        field_confidence={},
        document_type="unknown",
        tax_regime="unknown",
        raw_text=raw,
        method="none",
        provider=source,
        pages=pages,
        warnings=warnings,
    )
