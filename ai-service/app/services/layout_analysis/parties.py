from __future__ import annotations

import re

from app.models.document_bundle import DocumentSpan, LayoutRegion
from app.services.text_resolution.company_matching import company_matching_service

from .shared import page_height, page_width, region_from_spans

PARTY_SIGNAL_PATTERN = re.compile(
    r"\b(?:NIF|CIF|IVA|IGIC|CLIENTE|PROVEEDOR|EMISOR|RECEPTOR|DESTINATARIO|COMPRADOR)\b",
    re.IGNORECASE,
)
TAX_ID_PATTERN = re.compile(r"[A-Z]\d{7}[A-Z0-9]|\d{8}[A-Z]")


def build_party_regions(
    page_number: int,
    spans: list[DocumentSpan],
    company_context: dict[str, str],
) -> list[LayoutRegion]:
    header_candidates = _header_candidates(spans)
    if not header_candidates:
        return []

    regions: list[LayoutRegion] = []
    clusters = _cluster_header_columns(header_candidates, page_width(spans))

    if clusters:
        sorted_clusters = sorted(clusters, key=_cluster_center_x)
        if len(sorted_clusters) == 1:
            regions.append(region_from_spans(page_number, "header_left", sorted_clusters[0], confidence=0.58))
        else:
            regions.append(region_from_spans(page_number, "header_left", sorted_clusters[0], confidence=_cluster_confidence(sorted_clusters[0])))
            regions.append(region_from_spans(page_number, "header_right", sorted_clusters[-1], confidence=_cluster_confidence(sorted_clusters[-1])))

    company_spans = _company_anchor_spans(header_candidates, company_context)
    if company_spans:
        regions.append(region_from_spans(page_number, "company_anchor", company_spans, confidence=0.9))

    return regions


def _header_candidates(spans: list[DocumentSpan]) -> list[DocumentSpan]:
    current_height = page_height(spans)
    base_limit = max(280.0, current_height * 0.42)
    extended_limit = max(base_limit + 140.0, current_height * 0.62)

    candidates: list[DocumentSpan] = []
    for span in spans:
        if span.bbox.y0 <= base_limit:
            candidates.append(span)
            continue
        if span.bbox.y0 <= extended_limit and _looks_like_party_signal(span.text):
            candidates.append(span)
    return candidates


def _looks_like_party_signal(text: str) -> bool:
    compact = re.sub(r"\s+", " ", str(text or "").upper()).strip()
    if not compact:
        return False
    if PARTY_SIGNAL_PATTERN.search(compact):
        return True
    if TAX_ID_PATTERN.search(re.sub(r"[\s.\-]", "", compact)):
        return True
    letters = sum(char.isalpha() for char in compact)
    words = len(compact.split())
    return letters >= 8 and words >= 2


def _cluster_header_columns(spans: list[DocumentSpan], current_page_width: float) -> list[list[DocumentSpan]]:
    if len(spans) <= 2 or current_page_width <= 0:
        return [spans] if spans else []

    ordered_spans = sorted(
        spans,
        key=lambda span: (
            round(_span_center_x(span), 2),
            round(span.bbox.y0, 2),
            round(span.bbox.x0, 2),
            span.span_id,
        ),
    )
    centers = [(_span_center_x(span), span) for span in ordered_spans]
    min_gap = max(60.0, current_page_width * 0.08)
    clusters: list[list[DocumentSpan]] = [[centers[0][1]]]

    for index in range(1, len(centers)):
        previous_center = centers[index - 1][0]
        current_center = centers[index][0]
        if current_center - previous_center >= min_gap:
            clusters.append([])
        clusters[-1].append(centers[index][1])

    clusters = [cluster for cluster in clusters if cluster]
    if len(clusters) <= 2:
        return clusters or [spans]

    midpoint = current_page_width / 2.0
    left: list[DocumentSpan] = []
    right: list[DocumentSpan] = []
    for cluster in clusters:
        if _cluster_center_x(cluster) <= midpoint:
            left.extend(cluster)
        else:
            right.extend(cluster)

    merged_clusters = [cluster for cluster in (left, right) if cluster]
    if len(merged_clusters) >= 2:
        return merged_clusters
    return [clusters[0], clusters[-1]] if len(clusters) >= 2 else [spans]


def _company_anchor_spans(spans: list[DocumentSpan], company_context: dict[str, str]) -> list[DocumentSpan]:
    company = company_matching_service.normalize_company_context(company_context)
    company_tax_id = company_matching_service.clean_tax_id(company.get("tax_id", ""))
    company_anchor = company_matching_service.company_anchor_token(company.get("name", ""))
    if not company_tax_id and not company_anchor:
        return []

    matched_spans: list[DocumentSpan] = []
    for span in spans:
        normalized_span = company_matching_service.normalize_party_value(span.text)
        if company_tax_id and company_tax_id in normalized_span:
            matched_spans.append(span)
            continue
        if company_anchor and company_anchor in normalized_span:
            matched_spans.append(span)
    return matched_spans


def _cluster_confidence(cluster: list[DocumentSpan]) -> float:
    quality = 0.52
    quality += min(len(cluster), 6) * 0.04
    if any(_looks_like_party_signal(span.text) for span in cluster):
        quality += 0.08
    return min(0.82, round(quality, 2))


def _span_center_x(span: DocumentSpan) -> float:
    return (span.bbox.x0 + span.bbox.x1) / 2


def _cluster_center_x(cluster: list[DocumentSpan]) -> float:
    return sum(_span_center_x(span) for span in cluster) / max(1, len(cluster))
