"""Core party extraction helpers."""

from __future__ import annotations

import re

from app.utils.regex_patterns import CIF_NIF, CLIENTE, PROVEEDOR

from ..shared import looks_like_party_name
from .sections import (
    extract_customer_from_shipping_billing,
    extract_footer_legal_party,
    extract_parallel_party_sections,
    extract_party_section,
)


def extract_cifs(text: str) -> list[str]:
    results = []
    for match in CIF_NIF.finditer(text):
        cif = next(g for g in match.groups() if g is not None)
        cif_clean = re.sub(r"[\s\-]", "", cif).upper()
        if cif_clean not in results:
            results.append(cif_clean)
    return results


def extract_name(text: str, role: str) -> str:
    pattern = PROVEEDOR if role == "proveedor" else CLIENTE
    match = pattern.search(text)
    if match:
        name = match.group(1).strip().split("\t")[0].strip()
        if looks_like_party_name(name):
            return name[:200]
    return ""


def extract_parties_payload(text: str, lines: list[str]) -> dict[str, str]:
    result = {
        "proveedor": "",
        "cliente": "",
        "cif_proveedor": "",
        "cif_cliente": "",
    }

    parallel = extract_parallel_party_sections(lines)
    result.update({key: value for key, value in parallel.items() if value})

    if not result["proveedor"]:
        result["proveedor"], result["cif_proveedor"] = extract_party_section(lines, role="proveedor")
    if not result["cliente"]:
        result["cliente"], result["cif_cliente"] = extract_party_section(lines, role="cliente")

    shipping_customer, shipping_tax_id = extract_customer_from_shipping_billing(lines)
    footer_provider, footer_tax_id = extract_footer_legal_party(lines)

    if shipping_customer:
        result["cliente"] = shipping_customer
    if shipping_tax_id:
        result["cif_cliente"] = shipping_tax_id

    if footer_provider and (shipping_customer or not result["proveedor"]):
        result["proveedor"] = footer_provider
    if footer_tax_id and (shipping_customer or not result["cif_proveedor"]):
        result["cif_proveedor"] = footer_tax_id

    return result
