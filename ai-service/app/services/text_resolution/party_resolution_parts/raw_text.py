from __future__ import annotations

import re

from .shared import (
    is_generic_party_candidate,
    looks_like_address_or_contact_line,
    matches_company_context,
    normalize_party_name,
    party_candidate_score,
)
from .ticket import extract_ticket_parties

TAX_ID_PATTERN = re.compile(r"[A-Z]\d{7}[A-Z0-9]|\d{8}[A-Z]")
LEGAL_FOOTER_HINT = re.compile(r"\b(?:REGISTRO|MERCANTIL|INSCRIPC(?:ION|IÓN))\b", re.IGNORECASE)
LEGAL_NAME_NOISE = re.compile(r"^(?:REGISTRAD[OA]S?|INSCRIT[OA]S?|ADHERID[OA]S?)\b", re.IGNORECASE)


def extract_parties_from_raw_text(raw_text: str, company_context: dict[str, str] | None = None) -> dict[str, str]:
    result = {"proveedor": "", "cif_proveedor": "", "cliente": "", "cif_cliente": ""}
    if not raw_text:
        return result

    ticket_parties = extract_ticket_parties(raw_text, company_context=company_context)
    if any(ticket_parties.values()):
        return ticket_parties

    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    normalized_lines = [re.sub(r"\s+", " ", line).strip() for line in lines]
    compact_lines = [re.sub(r"[^A-Z0-9]", "", line.upper()) for line in normalized_lines]

    labeled_customer = _extract_labeled_customer(normalized_lines, compact_lines)

    header_end = _header_end_index(normalized_lines)
    party_blocks = _extract_header_party_blocks(
        normalized_lines[:header_end],
        company_context=company_context,
    )
    resolved = _resolve_party_roles(
        blocks=party_blocks,
        raw_text=raw_text,
        company_context=company_context,
        labeled_customer=labeled_customer,
    )
    result.update({key: value for key, value in resolved.items() if value})

    footer_party = extract_footer_legal_party(raw_text, company_context=company_context)
    if footer_party["name"] and (not result["proveedor"] or matches_company_context(result["proveedor"], result["cif_proveedor"], company_context)):
        result["proveedor"] = footer_party["name"]
    if footer_party["tax_id"] and (not result["cif_proveedor"] or matches_company_context(result["proveedor"], result["cif_proveedor"], company_context)):
        result["cif_proveedor"] = footer_party["tax_id"]

    if labeled_customer["name"] and not result["cliente"]:
        result["cliente"] = labeled_customer["name"]
    if labeled_customer["tax_id"] and not result["cif_cliente"]:
        result["cif_cliente"] = labeled_customer["tax_id"]

    return result


def _extract_header_party_blocks(lines: list[str], *, company_context: dict[str, str] | None = None) -> list[dict[str, object]]:
    if not lines:
        return []

    candidate_indexes = [index for index, line in enumerate(lines) if _looks_like_party_block_start(line)]
    if not candidate_indexes:
        return []

    blocks: list[dict[str, object]] = []
    for order, index in enumerate(candidate_indexes):
        stop_index = candidate_indexes[order + 1] if order + 1 < len(candidate_indexes) else len(lines)
        block_lines = lines[index:stop_index]
        candidate_name = normalize_party_name(lines[index])
        if not candidate_name:
            continue

        tax_id = ""
        context_lines: list[str] = []
        for candidate_line in block_lines[1:8]:
            if not tax_id:
                tax_ids = _extract_tax_ids(candidate_line)
                if tax_ids:
                    tax_id = tax_ids[0]
            if looks_like_address_or_contact_line(candidate_line):
                context_lines.append(candidate_line)

        score = party_candidate_score(candidate_name, tax_id)
        if tax_id:
            score += 2
        if context_lines:
            score += min(len(context_lines), 2)
        if len(candidate_name.split()) <= 2 and not tax_id and not context_lines:
            score -= 3
        role_hint = _infer_role_hint(lines, index)
        if role_hint == "proveedor":
            score += 1
        elif role_hint == "cliente":
            score += 1
        company_match = matches_company_context(candidate_name, tax_id, company_context)
        if company_match:
            score += 2

        blocks.append(
            {
                "name": candidate_name,
                "tax_id": tax_id,
                "score": score,
                "index": index,
                "role_hint": role_hint,
                "company_match": company_match,
                "has_context": bool(context_lines),
            }
        )

    return [block for block in sorted(blocks, key=lambda item: item["index"]) if int(block["score"]) > 0]


def _header_end_index(lines: list[str]) -> int:
    for index, line in enumerate(lines[:24]):
        compact = re.sub(r"[^A-Z0-9]", "", line.upper())
        if compact.startswith(("FACTURA", "DOCUMENTO", "FECHA", "CONCEPTO", "IMPORTE", "SUBTOTAL")):
            return index
    return min(len(lines), 18)


def _looks_like_party_block_start(value: str) -> bool:
    cleaned = normalize_party_name(value)
    if not cleaned:
        return False
    if is_generic_party_candidate(cleaned):
        return False
    if looks_like_address_or_contact_line(cleaned):
        return False
    if _extract_tax_ids(cleaned):
        return False

    upper_cleaned = cleaned.upper()
    if any(token in upper_cleaned for token in ("FACTURA", "DOCUMENTO", "FECHA", "CONCEPTO", "IMPORTE")):
        return False

    words = cleaned.split()
    if len(words) < 2:
        return False
    if len(words) == 2 and not re.search(r"\b(SL|S\.L\.|SA|S\.A\.|SLU|S\.L\.U\.|S\.C\.|PROFESIONAL)\b", upper_cleaned):
        return False
    return True


def _extract_labeled_customer(lines: list[str], compact_lines: list[str]) -> dict[str, str]:
    result = {"name": "", "tax_id": ""}
    cliente_index = next((i for i, compact in enumerate(compact_lines) if compact == "CLIENTE"), -1)
    cif_index = next((i for i, compact in enumerate(compact_lines) if compact in {"CIF", "CIFNIF"}), -1)

    if cliente_index > 0:
        candidate = lines[cliente_index - 1]
        if candidate and "DOMICILIO" not in candidate.upper():
            result["name"] = normalize_party_name(candidate)

    if cif_index >= 0:
        for candidate in lines[cif_index + 1:cif_index + 4]:
            tax_ids = _extract_tax_ids(candidate)
            if tax_ids:
                result["tax_id"] = tax_ids[0]
                break
    return result


def _resolve_party_roles(
    *,
    blocks: list[dict[str, object]],
    raw_text: str,
    company_context: dict[str, str] | None,
    labeled_customer: dict[str, str],
) -> dict[str, str]:
    result = {"proveedor": "", "cif_proveedor": "", "cliente": "", "cif_cliente": ""}
    if not blocks:
        return result

    sale_signal = _sale_signal(raw_text, labeled_customer)
    purchase_signal = _purchase_signal(raw_text)

    company_blocks = [block for block in blocks if block.get("company_match")]
    external_blocks = [block for block in blocks if not block.get("company_match")]

    if company_blocks and external_blocks:
        company_block = max(company_blocks, key=_block_rank)
        external_block = max(external_blocks, key=_block_rank)

        if _is_provider_hint(company_block) or _is_client_hint(external_block):
            _assign_roles(result, provider=company_block, client=external_block)
            return result
        if _is_client_hint(company_block) or _is_provider_hint(external_block):
            _assign_roles(result, provider=external_block, client=company_block)
            return result
        if purchase_signal > sale_signal:
            _assign_roles(result, provider=external_block, client=company_block)
            return result
        _assign_roles(result, provider=company_block, client=external_block)
        return result

    provider_block = next((block for block in blocks if _is_provider_hint(block)), None)
    client_block = next((block for block in blocks if _is_client_hint(block)), None)
    if provider_block:
        _assign_entity(result, "proveedor", provider_block)
    if client_block and client_block is not provider_block:
        _assign_entity(result, "cliente", client_block)

    if labeled_customer["name"] and not result["cliente"]:
        result["cliente"] = labeled_customer["name"]
        result["cif_cliente"] = labeled_customer["tax_id"]

    used_blocks = [block for block in (provider_block, client_block) if block is not None]
    remaining_blocks = [block for block in sorted(blocks, key=_block_rank, reverse=True) if block not in used_blocks]
    if not result["proveedor"] and remaining_blocks:
        _assign_entity(result, "proveedor", remaining_blocks[0])
        remaining_blocks = remaining_blocks[1:]
    if not result["cliente"] and remaining_blocks:
        _assign_entity(result, "cliente", remaining_blocks[0])

    return result


def _assign_roles(result: dict[str, str], *, provider: dict[str, object], client: dict[str, object]) -> None:
    _assign_entity(result, "proveedor", provider)
    _assign_entity(result, "cliente", client)


def _assign_entity(result: dict[str, str], role: str, block: dict[str, object]) -> None:
    result[role] = str(block.get("name", "") or "")
    result[f"cif_{role}"] = str(block.get("tax_id", "") or "")


def _infer_role_hint(lines: list[str], index: int) -> str:
    context = " ".join(lines[max(0, index - 2):index + 1]).upper()
    if any(token in context for token in ("CLIENTE", "DESTINATARIO", "COMPRADOR", "FACTURAR A")):
        return "cliente"
    if any(token in context for token in ("PROVEEDOR", "EMISOR", "RAZON SOCIAL", "RAZÓN SOCIAL")):
        return "proveedor"
    return ""


def _sale_signal(raw_text: str, labeled_customer: dict[str, str]) -> int:
    upper_text = (raw_text or "").upper()
    score = 0
    if labeled_customer["name"] or labeled_customer["tax_id"]:
        score += 4
    for token in ("CLIENTE", "DESTINATARIO", "COMPRADOR", "FACTURAR A"):
        if token in upper_text:
            score += 2
    if all(token in upper_text for token in ("FACTURA", "FECHA")) and any(
        token in upper_text for token in ("CONCEPTO", "IMPORTE", "TOTAL")
    ):
        score += 1
    return score


def _purchase_signal(raw_text: str) -> int:
    upper_text = (raw_text or "").upper()
    score = 0
    for token in ("DATOS DE FACTURACION", "DATOS DE FACTURACIÓN", "DATOS DE ENVIO", "DATOS DE ENVÍO", "ALBARAN", "ALBARÁN", "RETENCION", "RETENCIÓN", "IRPF"):
        if token in upper_text:
            score += 2
    for token in ("PROVEEDOR", "EMISOR"):
        if token in upper_text:
            score += 1
    return score


def _is_provider_hint(block: dict[str, object]) -> bool:
    return block.get("role_hint") == "proveedor"


def _is_client_hint(block: dict[str, object]) -> bool:
    return block.get("role_hint") == "cliente"


def _block_rank(block: dict[str, object]) -> tuple[float, int, int]:
    return (
        float(block.get("score", 0) or 0),
        1 if block.get("tax_id") else 0,
        len(str(block.get("name", "") or "")),
    )


def _extract_tax_ids(value: str) -> list[str]:
    compact_line = re.sub(r"[\s.\-]", "", str(value or "").upper())
    return [tax_id for tax_id in TAX_ID_PATTERN.findall(compact_line)]


def extract_footer_legal_party(raw_text: str, company_context: dict[str, str] | None = None) -> dict[str, str]:
    result = {"name": "", "tax_id": ""}
    if not raw_text:
        return result

    lines = [re.sub(r"\s+", " ", line).strip() for line in raw_text.splitlines() if line.strip()]
    tail_lines = lines[max(0, len(lines) - 24):]
    best_candidate: tuple[int, str, str] | None = None

    for local_index, line in enumerate(tail_lines):
        if not LEGAL_FOOTER_HINT.search(line):
            continue

        tax_ids = _extract_tax_ids(line)
        if not tax_ids:
            continue

        candidate_name = _extract_name_from_footer_line(line)
        if not candidate_name:
            for previous_line in reversed(tail_lines[max(0, local_index - 2):local_index]):
                normalized_previous = normalize_party_name(previous_line)
                if not normalized_previous or looks_like_address_or_contact_line(normalized_previous):
                    continue
                candidate_name = normalized_previous
                break

        if not candidate_name:
            continue

        clean_tax_id = tax_ids[0]
        if matches_company_context(candidate_name, clean_tax_id, company_context):
            continue

        score = party_candidate_score(candidate_name, clean_tax_id)
        upper_line = line.upper()
        if "REGISTRO" in upper_line or "MERCANTIL" in upper_line:
            score += 2
        if "CIF" in upper_line or "NIF" in upper_line:
            score += 1

        candidate = (score, candidate_name[:200], clean_tax_id)
        if best_candidate is None or candidate > best_candidate:
            best_candidate = candidate

    if best_candidate is None:
        return result
    result["name"] = best_candidate[1]
    result["tax_id"] = best_candidate[2]
    return result


def _extract_name_from_footer_line(value: str) -> str:
    candidate = re.split(r"\b(?:CIF|NIF)\b", value or "", maxsplit=1, flags=re.IGNORECASE)[0].strip(" -,:;")
    candidate = re.split(r"\bREGISTRO\b", candidate, maxsplit=1, flags=re.IGNORECASE)[0].strip(" -,:;")
    if " - " in candidate:
        candidate = candidate.split(" - ", 1)[0].strip(" -,:;")
    if LEGAL_NAME_NOISE.match(candidate):
        return ""

    normalized_candidate = normalize_party_name(candidate)
    if normalized_candidate and not looks_like_address_or_contact_line(normalized_candidate):
        return candidate[:200]
    return ""
