from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from app.services.document_intelligence import document_intelligence_service


ROOT = Path(__file__).resolve().parent
CASES_PATH = ROOT / "cases.json"


def _load_cases() -> list[dict[str, Any]]:
    with CASES_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").upper().split())


def _contains(actual: Any, expected_snippet: str) -> bool:
    return _normalize_text(expected_snippet) in _normalize_text(actual)


def _approx_equal(actual: Any, expected: float, tolerance: float = 0.05) -> bool:
    try:
        return abs(float(actual) - float(expected)) <= tolerance
    except (TypeError, ValueError):
        return False


def _line_sum(lines: list[dict[str, Any]]) -> float:
    total = 0.0
    for line in lines or []:
        try:
            total += float(line.get("importe", 0) or 0)
        except (TypeError, ValueError):
            continue
    return round(total, 2)


def _collect_mismatches(result: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    data = result["data"].model_dump()
    normalized = result["normalized_document"].model_dump()
    mismatches: list[str] = []

    exact_text_fields = (
        "numero_factura",
        "tipo_factura",
        "fecha",
        "cif_proveedor",
        "cif_cliente",
    )
    for field in exact_text_fields:
        if field in expected and _normalize_text(data.get(field)) != _normalize_text(expected[field]):
            mismatches.append(f"{field}: esperado={expected[field]!r} real={data.get(field)!r}")

    contains_fields = (
        ("proveedor", "proveedor_contains"),
        ("cliente", "cliente_contains"),
    )
    for actual_field, expected_field in contains_fields:
        if expected_field in expected and not _contains(data.get(actual_field), expected[expected_field]):
            mismatches.append(
                f"{actual_field}: esperado contiene {expected[expected_field]!r} real={data.get(actual_field)!r}"
            )

    numeric_fields = (
        "base_imponible",
        "iva_porcentaje",
        "iva",
        "retencion_porcentaje",
        "retencion",
        "total",
    )
    for field in numeric_fields:
        if field in expected and not _approx_equal(data.get(field, 0), expected[field]):
            mismatches.append(f"{field}: esperado={expected[field]} real={data.get(field)}")

    if "document_type" in expected:
        actual_document_type = normalized.get("classification", {}).get("document_type", "")
        if actual_document_type != expected["document_type"]:
            mismatches.append(
                f"document_type: esperado={expected['document_type']!r} real={actual_document_type!r}"
            )

    normalized_party_fields = (
        ("issuer", "issuer_contains", "issuer_tax_id"),
        ("recipient", "recipient_contains", "recipient_tax_id"),
    )
    for role, contains_field, tax_field in normalized_party_fields:
        actual_party = normalized.get(role, {})
        if contains_field in expected and not _contains(actual_party.get("name", ""), expected[contains_field]):
            mismatches.append(
                f"{role}.name: esperado contiene {expected[contains_field]!r} real={actual_party.get('name')!r}"
            )
        if tax_field in expected and _normalize_text(actual_party.get("tax_id")) != _normalize_text(expected[tax_field]):
            mismatches.append(
                f"{role}.tax_id: esperado={expected[tax_field]!r} real={actual_party.get('tax_id')!r}"
            )

    if "withholding_total" in expected:
        actual_withholding_total = normalized.get("totals", {}).get("withholding_total", 0)
        if not _approx_equal(actual_withholding_total, expected["withholding_total"]):
            mismatches.append(
                f"withholding_total: esperado={expected['withholding_total']} real={actual_withholding_total}"
            )

    if "withholding_count" in expected:
        actual_withholding_count = len(normalized.get("withholdings", []) or [])
        if actual_withholding_count != expected["withholding_count"]:
            mismatches.append(
                f"withholding_count: esperado={expected['withholding_count']} real={actual_withholding_count}"
            )

    if "normalized_subtotal" in expected:
        actual_subtotal = normalized.get("totals", {}).get("subtotal", 0)
        if not _approx_equal(actual_subtotal, expected["normalized_subtotal"]):
            mismatches.append(
                f"normalized_subtotal: esperado={expected['normalized_subtotal']} real={actual_subtotal}"
            )

    if "rectified_invoice_number" in expected:
        actual_rectified = normalized.get("identity", {}).get("rectified_invoice_number", "")
        if _normalize_text(actual_rectified) != _normalize_text(expected["rectified_invoice_number"]):
            mismatches.append(
                f"rectified_invoice_number: esperado={expected['rectified_invoice_number']!r} real={actual_rectified!r}"
            )

    actual_lines = data.get("lineas", [])
    if "line_count" in expected and len(actual_lines) != expected["line_count"]:
        mismatches.append(f"line_count: esperado={expected['line_count']} real={len(actual_lines)}")

    if "line_total_sum" in expected:
        actual_line_sum = _line_sum(actual_lines)
        if not _approx_equal(actual_line_sum, expected["line_total_sum"]):
            mismatches.append(
                f"line_total_sum: esperado={expected['line_total_sum']} real={actual_line_sum}"
            )

    for snippet in expected.get("line_descriptions_contain", []):
        if not any(_contains(line.get("descripcion", ""), snippet) for line in actual_lines):
            mismatches.append(f"line_descriptions_contain: falta {snippet!r}")

    return mismatches


async def _run_case(case: dict[str, Any]) -> dict[str, Any]:
    file_path = ROOT / case["file"]
    result = await document_intelligence_service.extract(
        str(file_path),
        filename=file_path.name,
        mime_type=case.get("mime_type", "application/octet-stream"),
        company_context=case.get("company_context"),
    )
    mismatches = _collect_mismatches(result, case["expected"])
    return {
        "id": case["id"],
        "ok": not mismatches,
        "mismatches": mismatches,
        "summary": {
            "numero_factura": result["data"].numero_factura,
            "tipo_factura": result["data"].tipo_factura,
            "fecha": result["data"].fecha,
            "proveedor": result["data"].proveedor,
            "cliente": result["data"].cliente,
            "base_imponible": result["data"].base_imponible,
            "iva_porcentaje": result["data"].iva_porcentaje,
            "iva": result["data"].iva,
            "retencion": result["data"].retencion,
            "total": result["data"].total,
            "confianza": result["data"].confianza,
        },
    }


async def _main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", help="ID de un caso concreto")
    args = parser.parse_args()

    cases = _load_cases()
    if args.case:
        cases = [case for case in cases if case["id"] == args.case]
        if not cases:
            raise SystemExit(f"Caso no encontrado: {args.case}")

    results = []
    for case in cases:
        print(f"\n==> Ejecutando {case['id']}")
        outcome = await _run_case(case)
        results.append(outcome)
        if outcome["ok"]:
            print("OK")
        else:
            print("FAIL")
            for mismatch in outcome["mismatches"]:
                print(f" - {mismatch}")

    passed = sum(1 for result in results if result["ok"])
    total = len(results)
    print(f"\nResumen: {passed}/{total} casos correctos")

    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
