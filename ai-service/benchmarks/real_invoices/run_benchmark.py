from __future__ import annotations

import argparse
import asyncio
import difflib
import json
import re
import sys
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path
from typing import Any

APP_ROOT = Path(__file__).resolve().parents[2]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.config import settings
from app.models.document_bundle import DocumentBundle
from app.models.extraction_result import ExtractionResult
from app.services.document_intelligence import document_intelligence_service
from app.services.document_intelligence_flow.helpers import merge_with_fallback
from app.services.field_extractor import field_extractor
from app.services.text_resolution.normalization import invoice_normalization_service


ROOT = Path(__file__).resolve().parent
CASES_PATH = ROOT / "cases.json"

BENCHMARK_ROUTES: dict[str, dict[str, Any]] = {
    "configured": {},
    "local_only": {
        "document_parser_provider": "local",
        "document_parser_force_provider": "local",
        "document_parser_fallback_enabled": False,
        "document_parser_fallback_provider": "local",
    },
    "mistral_primary": {
        "document_parser_provider": "mistral",
        "document_parser_force_provider": "",
        "document_parser_fallback_enabled": True,
        "document_parser_fallback_provider": "local",
    },
    "mistral_only": {
        "document_parser_provider": "mistral",
        "document_parser_force_provider": "mistral",
        "document_parser_fallback_enabled": False,
        "document_parser_fallback_provider": "local",
    },
}


def _load_cases(cases_path: Path = CASES_PATH) -> list[dict[str, Any]]:
    with cases_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _resolve_case_file_path(cases_root: Path, file_ref: str) -> Path:
    path = Path(file_ref)
    if path.is_absolute():
        return path
    return cases_root / path


def _load_case_raw_text(case: dict[str, Any], cases_root: Path) -> str:
    if "raw_text" in case:
        return str(case.get("raw_text") or "")
    if "raw_text_file" in case:
        return _resolve_case_file_path(cases_root, str(case["raw_text_file"])).read_text(encoding="utf-8")
    return ""


def _build_synthetic_input_profile(case: dict[str, Any], raw_text: str) -> dict[str, Any]:
    default_steps = ["synthetic_raw_text"]
    if "\f" in raw_text:
        default_steps.append("synthetic_page_breaks")
    return {
        "source_channel": "benchmark",
        "input_kind": case.get("input_kind", "synthetic_text"),
        "text_source": case.get("text_source", "synthetic_text"),
        "ocr_engine": "",
        "document_family_hint": case.get("document_family_hint", ""),
        "preprocessing_steps": list(case.get("preprocessing_steps") or default_steps),
    }


def _build_synthetic_case_result(case: dict[str, Any], cases_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    raw_text = _load_case_raw_text(case, cases_root)
    if not raw_text.strip():
        raise RuntimeError(f"Caso sintetico sin texto: {case.get('id', '<sin-id>')}")

    company_context = case.get("company_context")
    page_count = max(1, raw_text.count("\f") + 1)
    bundle = DocumentBundle(raw_text=raw_text, page_count=page_count)
    bundle.refresh_derived_state()

    fallback_data = document_intelligence_service._heuristic_extract(raw_text)
    bundle_candidate, _bundle_sources = field_extractor.extract_from_bundle(bundle)
    data = merge_with_fallback(bundle_candidate, fallback_data)
    data, warnings = invoice_normalization_service.normalize_invoice_data(
        data,
        fallback_data,
        raw_text=raw_text,
        company_context=company_context,
    )
    resolution = document_intelligence_service._build_resolution(
        data=data,
        raw_text=raw_text,
        filename=case.get("synthetic_name", f"{case['id']}.txt"),
        mime_type=case.get("mime_type", "text/plain"),
        pages=page_count,
        input_profile=_build_synthetic_input_profile(case, raw_text),
        bundle=bundle,
        fallback_data=fallback_data,
        bundle_candidate=bundle_candidate,
        ai_candidate=None,
        provider="synthetic_text",
        method="raw_text_benchmark",
        warnings=warnings,
        company_context=company_context,
    )
    return {
        "data": resolution["data"],
        "normalized_document": resolution["normalized_document"],
    }, {
        "provider": "synthetic_text",
        "input_provider": "synthetic_text",
        "fallback_applied": False,
    }


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").upper().split())


def _contains(actual: Any, expected_snippet: str) -> bool:
    return _normalize_text(expected_snippet) in _normalize_text(actual)


def _tokenize_text(value: Any) -> list[str]:
    return [token for token in re.findall(r"[A-Z0-9]+", _normalize_text(value)) if token]


def _fuzzy_contains_text(actual: Any, expected_snippet: str) -> bool:
    if _contains(actual, expected_snippet):
        return True

    expected_tokens = _tokenize_text(expected_snippet)
    actual_tokens = _tokenize_text(actual)
    if not expected_tokens or not actual_tokens:
        return False

    matched_tokens = 0
    for expected_token in expected_tokens:
        best_ratio = max(
            (
                difflib.SequenceMatcher(a=expected_token, b=actual_token).ratio()
                for actual_token in actual_tokens
            ),
            default=0.0,
        )
        if best_ratio >= 0.8:
            matched_tokens += 1

    return matched_tokens >= len(expected_tokens)


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


def _build_check(
    *,
    field: str,
    ok: bool,
    actual: Any,
    expected: Any,
    family: str,
) -> dict[str, Any]:
    return {
        "field": field,
        "ok": bool(ok),
        "actual": actual,
        "expected": expected,
        "family": family,
    }


def _result_to_payload(result: ExtractionResult | dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    if isinstance(result, ExtractionResult):
        return result.data.model_dump(), result.normalized_document.model_dump()

    data = result.get("data")
    normalized = result.get("normalized_document")
    if hasattr(data, "model_dump"):
        data = data.model_dump()
    if hasattr(normalized, "model_dump"):
        normalized = normalized.model_dump()
    return data or {}, normalized or {}


def _collect_checks(result: ExtractionResult | dict[str, Any], case: dict[str, Any]) -> list[dict[str, Any]]:
    expected = case["expected"]
    family = case.get("family", "generic")
    data, normalized = _result_to_payload(result)
    checks: list[dict[str, Any]] = []

    exact_text_fields = (
        "numero_factura",
        "tipo_factura",
        "fecha",
        "cif_proveedor",
        "cif_cliente",
    )
    for field in exact_text_fields:
        if field in expected:
            checks.append(
                _build_check(
                    field=f"legacy.{field}",
                    ok=_normalize_text(data.get(field)) == _normalize_text(expected[field]),
                    actual=data.get(field),
                    expected=expected[field],
                    family=family,
                )
            )

    contains_fields = (
        ("proveedor", "proveedor_contains"),
        ("cliente", "cliente_contains"),
    )
    for actual_field, expected_field in contains_fields:
        if expected_field in expected:
            checks.append(
                _build_check(
                    field=f"legacy.{actual_field}",
                    ok=_contains(data.get(actual_field), expected[expected_field]),
                    actual=data.get(actual_field),
                    expected=f"contains:{expected[expected_field]}",
                    family=family,
                )
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
        if field in expected:
            checks.append(
                _build_check(
                    field=f"legacy.{field}",
                    ok=_approx_equal(data.get(field, 0), expected[field]),
                    actual=data.get(field),
                    expected=expected[field],
                    family=family,
                )
            )

    if "document_type" in expected:
        actual_document_type = normalized.get("classification", {}).get("document_type", "")
        checks.append(
            _build_check(
                field="normalized.classification.document_type",
                ok=actual_document_type == expected["document_type"],
                actual=actual_document_type,
                expected=expected["document_type"],
                family=family,
            )
        )

    normalized_party_fields = (
        ("issuer", "issuer_contains", "issuer_tax_id"),
        ("recipient", "recipient_contains", "recipient_tax_id"),
    )
    for role, contains_field, tax_field in normalized_party_fields:
        actual_party = normalized.get(role, {})
        if contains_field in expected:
            checks.append(
                _build_check(
                    field=f"normalized.{role}.name",
                    ok=_contains(actual_party.get("name", ""), expected[contains_field]),
                    actual=actual_party.get("name"),
                    expected=f"contains:{expected[contains_field]}",
                    family=family,
                )
            )
        if tax_field in expected:
            checks.append(
                _build_check(
                    field=f"normalized.{role}.tax_id",
                    ok=_normalize_text(actual_party.get("tax_id")) == _normalize_text(expected[tax_field]),
                    actual=actual_party.get("tax_id"),
                    expected=expected[tax_field],
                    family=family,
                )
            )

    if "withholding_total" in expected:
        actual_withholding_total = normalized.get("totals", {}).get("withholding_total", 0)
        checks.append(
            _build_check(
                field="normalized.totals.withholding_total",
                ok=_approx_equal(actual_withholding_total, expected["withholding_total"]),
                actual=actual_withholding_total,
                expected=expected["withholding_total"],
                family=family,
            )
        )

    if "withholding_count" in expected:
        actual_withholding_count = len(normalized.get("withholdings", []) or [])
        checks.append(
            _build_check(
                field="normalized.withholdings.count",
                ok=actual_withholding_count == expected["withholding_count"],
                actual=actual_withholding_count,
                expected=expected["withholding_count"],
                family=family,
            )
        )

    if "normalized_subtotal" in expected:
        actual_subtotal = normalized.get("totals", {}).get("subtotal", 0)
        checks.append(
            _build_check(
                field="normalized.totals.subtotal",
                ok=_approx_equal(actual_subtotal, expected["normalized_subtotal"]),
                actual=actual_subtotal,
                expected=expected["normalized_subtotal"],
                family=family,
            )
        )

    if "rectified_invoice_number" in expected:
        actual_rectified = normalized.get("identity", {}).get("rectified_invoice_number", "")
        checks.append(
            _build_check(
                field="normalized.identity.rectified_invoice_number",
                ok=_normalize_text(actual_rectified) == _normalize_text(expected["rectified_invoice_number"]),
                actual=actual_rectified,
                expected=expected["rectified_invoice_number"],
                family=family,
            )
        )

    actual_lines = data.get("lineas", [])
    if "line_count" in expected:
        checks.append(
            _build_check(
                field="legacy.lineas.count",
                ok=len(actual_lines) == expected["line_count"],
                actual=len(actual_lines),
                expected=expected["line_count"],
                family=family,
            )
        )

    if "line_total_sum" in expected:
        actual_line_sum = _line_sum(actual_lines)
        checks.append(
            _build_check(
                field="legacy.lineas.sum_importe",
                ok=_approx_equal(actual_line_sum, expected["line_total_sum"]),
                actual=actual_line_sum,
                expected=expected["line_total_sum"],
                family=family,
            )
        )

    for snippet in expected.get("line_descriptions_contain", []):
        checks.append(
            _build_check(
                field="legacy.lineas.descripcion",
                ok=any(_fuzzy_contains_text(line.get("descripcion", ""), snippet) for line in actual_lines),
                actual=[line.get("descripcion", "") for line in actual_lines],
                expected=f"contains:{snippet}",
                family=family,
            )
        )

    return checks


def _format_mismatch(check: dict[str, Any]) -> str:
    return f"{check['field']}: esperado={check['expected']!r} real={check['actual']!r}"


def _build_field_summary(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {"passed": 0, "total": 0})
    for check in checks:
        item = grouped[check["field"]]
        item["total"] += 1
        if check["ok"]:
            item["passed"] += 1

    summary = []
    for field, item in grouped.items():
        total = item["total"]
        passed = item["passed"]
        summary.append(
            {
                "field": field,
                "passed": passed,
                "total": total,
                "ratio": round(passed / total, 4) if total else 0.0,
            }
        )
    summary.sort(key=lambda item: (item["ratio"], item["field"]))
    return summary


def _build_family_summary(outcomes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"cases_passed": 0, "cases_total": 0, "checks_passed": 0, "checks_total": 0}
    )
    for outcome in outcomes:
        family = outcome["family"]
        item = grouped[family]
        item["cases_total"] += 1
        item["checks_total"] += len(outcome["checks"])
        item["checks_passed"] += sum(1 for check in outcome["checks"] if check["ok"])
        if outcome["ok"]:
            item["cases_passed"] += 1

    summary = []
    for family, item in grouped.items():
        summary.append(
            {
                "family": family,
                "cases_passed": item["cases_passed"],
                "cases_total": item["cases_total"],
                "case_ratio": round(item["cases_passed"] / item["cases_total"], 4) if item["cases_total"] else 0.0,
                "checks_passed": item["checks_passed"],
                "checks_total": item["checks_total"],
                "check_ratio": round(item["checks_passed"] / item["checks_total"], 4) if item["checks_total"] else 0.0,
            }
        )
    summary.sort(key=lambda item: (item["case_ratio"], item["family"]))
    return summary


def _build_route_overrides(route: str) -> dict[str, Any]:
    if route not in BENCHMARK_ROUTES:
        raise ValueError(f"Ruta benchmark no soportada: {route}")
    return dict(BENCHMARK_ROUTES[route])


@contextmanager
def _settings_overrides(route: str):
    overrides = _build_route_overrides(route)
    original = {key: getattr(settings, key) for key in overrides}
    try:
        for key, value in overrides.items():
            setattr(settings, key, value)
        yield overrides
    finally:
        for key, value in original.items():
            setattr(settings, key, value)


async def _run_case(case: dict[str, Any], cases_root: Path) -> dict[str, Any]:
    try:
        if "raw_text" in case or "raw_text_file" in case:
            result, summary_meta = _build_synthetic_case_result(case, cases_root)
        else:
            file_path = _resolve_case_file_path(cases_root, str(case["file"]))
            result = await document_intelligence_service.extract(
                str(file_path),
                filename=file_path.name,
                mime_type=case.get("mime_type", "application/octet-stream"),
                company_context=case.get("company_context"),
            )
            summary_meta = {
                "provider": result.provider,
                "input_provider": result.document_input.document_provider,
                "fallback_applied": result.document_input.fallback_applied,
            }

        checks = _collect_checks(result, case)
        failed_checks = [check for check in checks if not check["ok"]]
        data, _normalized = _result_to_payload(result)
        return {
            "id": case["id"],
            "family": case.get("family", "generic"),
            "ok": not failed_checks,
            "checks": checks,
            "mismatches": [_format_mismatch(check) for check in failed_checks],
            "summary": {
                "numero_factura": data.get("numero_factura"),
                "tipo_factura": data.get("tipo_factura"),
                "fecha": data.get("fecha"),
                "proveedor": data.get("proveedor"),
                "cliente": data.get("cliente"),
                "base_imponible": data.get("base_imponible"),
                "iva_porcentaje": data.get("iva_porcentaje"),
                "iva": data.get("iva"),
                "retencion": data.get("retencion"),
                "total": data.get("total"),
                "confianza": data.get("confianza"),
                **summary_meta,
            },
        }
    except Exception as exc:
        return {
            "id": case["id"],
            "family": case.get("family", "generic"),
            "ok": False,
            "checks": [],
            "mismatches": [f"runtime_error: {type(exc).__name__}: {exc}"],
            "summary": {
                "provider": "",
                "input_provider": "",
                "fallback_applied": False,
            },
        }


async def _run_suite(cases: list[dict[str, Any]], route: str, cases_root: Path) -> dict[str, Any]:
    with _settings_overrides(route) as applied_overrides:
        outcomes = []
        for case in cases:
            print(f"\n==> [{route}] Ejecutando {case['id']}")
            outcome = await _run_case(case, cases_root)
            outcomes.append(outcome)
            if outcome["ok"]:
                print("OK")
            else:
                print("FAIL")
                for mismatch in outcome["mismatches"]:
                    print(f" - {mismatch}")

    all_checks = [check for outcome in outcomes for check in outcome["checks"]]
    passed_cases = sum(1 for outcome in outcomes if outcome["ok"])
    total_cases = len(outcomes)
    passed_checks = sum(1 for check in all_checks if check["ok"])
    total_checks = len(all_checks)

    return {
        "route": route,
        "applied_overrides": applied_overrides,
        "cases_passed": passed_cases,
        "cases_total": total_cases,
        "case_ratio": round(passed_cases / total_cases, 4) if total_cases else 0.0,
        "checks_passed": passed_checks,
        "checks_total": total_checks,
        "check_ratio": round(passed_checks / total_checks, 4) if total_checks else 0.0,
        "field_summary": _build_field_summary(all_checks),
        "family_summary": _build_family_summary(outcomes),
        "results": outcomes,
    }


def _print_suite_summary(summary: dict[str, Any]) -> None:
    print(
        f"\nResumen [{summary['route']}]: "
        f"{summary['cases_passed']}/{summary['cases_total']} casos correctos | "
        f"{summary['checks_passed']}/{summary['checks_total']} checks correctos"
    )
    print("\nFamilias:")
    for item in summary["family_summary"]:
        print(
            f" - {item['family']}: "
            f"{item['cases_passed']}/{item['cases_total']} casos | "
            f"{item['checks_passed']}/{item['checks_total']} checks"
        )

    print("\nCampos:")
    for item in summary["field_summary"]:
        print(f" - {item['field']}: {item['passed']}/{item['total']}")


def _print_route_comparison(summaries: list[dict[str, Any]]) -> None:
    if len(summaries) <= 1:
        return
    print("\nComparativa de rutas:")
    for summary in summaries:
        print(
            f" - {summary['route']}: "
            f"{summary['cases_passed']}/{summary['cases_total']} casos | "
            f"{summary['checks_passed']}/{summary['checks_total']} checks"
        )


def _filter_cases(
    cases: list[dict[str, Any]],
    *,
    case_id: str | None,
    family: str | None,
    tag: str | None,
) -> list[dict[str, Any]]:
    filtered = cases
    if case_id:
        filtered = [case for case in filtered if case["id"] == case_id]
        if not filtered:
            raise SystemExit(f"Caso no encontrado: {case_id}")
    if family:
        filtered = [case for case in filtered if case.get("family") == family]
        if not filtered:
            raise SystemExit(f"Familia no encontrada: {family}")
    if tag:
        filtered = [case for case in filtered if tag in (case.get("tags") or [])]
        if not filtered:
            raise SystemExit(f"Tag no encontrado: {tag}")
    return filtered


async def _main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", help="ID de un caso concreto")
    parser.add_argument("--family", help="Familia documental a ejecutar")
    parser.add_argument("--tag", help="Tag de escenario a ejecutar")
    parser.add_argument("--cases-path", help="Ruta opcional a otro cases.json")
    parser.add_argument(
        "--route",
        action="append",
        choices=sorted(BENCHMARK_ROUTES.keys()),
        help="Ruta de benchmark a ejecutar. Se puede repetir.",
    )
    parser.add_argument("--json-out", help="Ruta opcional para guardar el resumen JSON")
    args = parser.parse_args()

    routes = args.route or ["configured"]
    selected_cases_path = Path(args.cases_path) if args.cases_path else CASES_PATH
    cases_root = selected_cases_path.parent
    cases = _filter_cases(
        _load_cases(selected_cases_path),
        case_id=args.case,
        family=args.family,
        tag=args.tag,
    )

    summaries = []
    for route in routes:
        summary = await _run_suite(cases, route, cases_root)
        summaries.append(summary)
        _print_suite_summary(summary)

    _print_route_comparison(summaries)

    if args.json_out:
        output_path = Path(args.json_out)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any]
        if len(summaries) == 1:
            payload = summaries[0]
        else:
            payload = {"routes": summaries}
        output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    return 0 if all(summary["cases_passed"] == summary["cases_total"] for summary in summaries) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
