#!/usr/bin/env python3
"""
Batch tester for the ai-service-vision engine.

Usage:
    python test_batch_local.py [FOLDER] [--n 5] [--url http://localhost:8001]

    FOLDER   Path to folder containing invoice images/PDFs (default: ../../storage/uploads on Desktop).
    --n N    Process N files at a time (default 5).
    --url    Base URL of the running ai-service-vision (default http://localhost:8001).

Examples:
    # Test first 5 files from uploads folder
    python test_batch_local.py

    # Test a specific folder, batches of 3
    python test_batch_local.py C:/Users/raule/Desktop/storage/uploads --n 3

    # Test a single file
    python test_batch_local.py --file C:/path/to/invoice.jpeg
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

AI_URL = "http://localhost:8001"
SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".webp", ".JPG", ".JPEG"}

# Default company context (from .env COMPANY_ADDITIONAL_TAX_IDS)
DEFAULT_COMPANY_TAX_ID = "B35222249"
DEFAULT_COMPANY_NAME = ""


def process_file(file_path: Path, base_url: str, company_tax_id: str, company_name: str) -> dict:
    """POST a single file to /ai/process and return the result."""
    mime = "application/pdf" if file_path.suffix.lower() == ".pdf" else "image/jpeg"
    with open(file_path, "rb") as f:
        resp = requests.post(
            f"{base_url}/ai/process",
            files={"file": (file_path.name, f, mime)},
            data={
                "mime_type": mime,
                "company_name": company_name,
                "company_tax_id": company_tax_id,
            },
            timeout=180,
        )
    resp.raise_for_status()
    return resp.json()


def summarize(result: dict) -> str:
    """One-line human summary of a processed result."""
    if not result.get("success"):
        return "  ERROR — no success flag"

    nd = result.get("normalized_document") or {}
    identity = nd.get("identity") or {}
    totals = nd.get("totals") or {}
    tax_bd = nd.get("tax_breakdown") or []
    lines = result.get("lineas") or []

    parts = [
        f"  Nº factura  : {identity.get('invoice_number') or result.get('numero_factura') or '—'}",
        f"  Fecha       : {identity.get('issue_date') or result.get('fecha') or '—'}",
        f"  Emisor      : {(nd.get('issuer') or {}).get('name') or result.get('proveedor') or '—'}",
        f"  Receptor    : {(nd.get('recipient') or {}).get('name') or result.get('cliente') or '—'}",
        f"  Base        : {totals.get('subtotal', '—')}",
        f"  Impuesto    : {totals.get('tax_total', '—')}  ({len(tax_bd)} tramo(s))",
        f"  Retención   : {totals.get('withholding_total', '—')}",
        f"  TOTAL       : {totals.get('total', '—')}",
        f"  Líneas      : {len(lines)}",
        f"  Régimen     : {result.get('tax_regime') or '—'}",
        f"  Lado        : {result.get('operation_side') or '—'}",
        f"  Modelo      : {result.get('provider') or '—'}",
        f"  Tiempo      : {(nd.get('document_meta') or {}).get('elapsed_seconds') or '—'}s",
    ]

    # Warn about suspicious data
    warnings: list[str] = []
    if not (identity.get("invoice_number") or result.get("numero_factura")):
        warnings.append("⚠ SIN NÚMERO DE FACTURA")
    if not (identity.get("issue_date") or result.get("fecha")):
        warnings.append("⚠ SIN FECHA")
    if totals.get("total", 0) == 0:
        warnings.append("⚠ TOTAL = 0")
    if len(tax_bd) == 0:
        warnings.append("⚠ SIN DESGLOSE IMPUESTOS")
    if len(lines) == 0:
        warnings.append("⚠ SIN LÍNEAS")

    if warnings:
        parts.append("  " + " | ".join(warnings))

    return "\n".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch tester for ai-service-vision")
    parser.add_argument(
        "folder",
        nargs="?",
        default=str(Path.home() / "Desktop" / "storage" / "uploads"),
        help="Folder with invoice files",
    )
    parser.add_argument("--n", type=int, default=5, help="Batch size (default 5)")
    parser.add_argument("--url", default=AI_URL, help="AI service base URL")
    parser.add_argument("--file", default="", help="Process a single specific file")
    parser.add_argument("--tax-id", default=DEFAULT_COMPANY_TAX_ID, help="Company tax ID for side detection")
    parser.add_argument("--company", default=DEFAULT_COMPANY_NAME, help="Company name for side detection")
    parser.add_argument("--save-json", action="store_true", help="Save each result as JSON alongside the file")
    parser.add_argument("--offset", type=int, default=0, help="Skip first N files (for sequential batches)")
    args = parser.parse_args()

    # Health check
    try:
        health = requests.get(f"{args.url}/health", timeout=5).json()
        print(f"✓ Service healthy: {health}\n")
    except Exception as e:
        print(f"✗ Cannot reach {args.url}: {e}")
        sys.exit(1)

    if args.file:
        files_to_process = [Path(args.file)]
    else:
        folder = Path(args.folder)
        if not folder.exists():
            print(f"Folder not found: {folder}")
            sys.exit(1)
        all_files = sorted(
            [f for f in folder.iterdir() if f.suffix in SUPPORTED_EXTENSIONS and f.is_file()]
        )
        files_to_process = all_files[args.offset: args.offset + args.n]

    if not files_to_process:
        print("No files found.")
        sys.exit(0)

    print(f"Processing {len(files_to_process)} file(s) from offset {args.offset}:\n")

    results_summary: list[dict] = []
    total_time = 0.0
    errors = 0

    for i, fp in enumerate(files_to_process, 1):
        print(f"[{i}/{len(files_to_process)}] {fp.name}")
        t0 = time.time()
        try:
            result = process_file(fp, args.url, args.tax_id, args.company)
            elapsed = round(time.time() - t0, 2)
            total_time += elapsed
            print(summarize(result))

            if args.save_json:
                out_path = fp.with_suffix(".result.json")
                out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
                print(f"  → Saved: {out_path.name}")

            results_summary.append({
                "file": fp.name,
                "ok": True,
                "elapsed": elapsed,
                "numero_factura": result.get("numero_factura") or "",
                "total": (result.get("normalized_document") or {}).get("totals", {}).get("total"),
                "lines": len(result.get("lineas") or []),
                "tax_rows": len((result.get("normalized_document") or {}).get("tax_breakdown") or []),
            })

        except Exception as e:
            elapsed = round(time.time() - t0, 2)
            total_time += elapsed
            errors += 1
            print(f"  ✗ ERROR: {e}")
            results_summary.append({"file": fp.name, "ok": False, "error": str(e), "elapsed": elapsed})

        print()

    # Summary table
    print("=" * 60)
    print(f"RESUMEN: {len(files_to_process)} facturas | {errors} errores | {total_time:.1f}s total | {total_time/len(files_to_process):.1f}s media")
    print("=" * 60)
    for r in results_summary:
        status = "✓" if r["ok"] else "✗"
        if r["ok"]:
            print(f"  {status} {r['file']:<45} Nº={r['numero_factura']:<15} Total={r['total']}  Líneas={r['lines']}  Tramos={r['tax_rows']}  {r['elapsed']}s")
        else:
            print(f"  {status} {r['file']:<45} ERROR: {r.get('error','?')}")


if __name__ == "__main__":
    main()
