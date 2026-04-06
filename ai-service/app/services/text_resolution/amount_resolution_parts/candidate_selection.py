from __future__ import annotations

from app.models.invoice_model import InvoiceData


def pick_best_amounts(data: InvoiceData, line_sum: float) -> tuple[float, float] | None:
    candidates: list[tuple[float, float]] = []
    withholding = round(max(0, data.retencion or 0), 2)

    if data.base_imponible > 0:
        candidates.append((round(data.base_imponible, 2), round(max(0, data.iva), 2)))
    if line_sum > 0:
        if data.iva_porcentaje > 0:
            candidates.append((line_sum, round(line_sum * data.iva_porcentaje / 100, 2)))
        if data.total > 0:
            gross_total = round(data.total + withholding, 2) if withholding > 0 else data.total
            candidates.append((line_sum, round(max(0, gross_total - line_sum), 2)))
    if data.total > 0 and data.iva > 0:
        gross_total = round(data.total + withholding, 2) if withholding > 0 else data.total
        candidates.append((round(max(0, gross_total - data.iva), 2), round(data.iva, 2)))
    if data.total > 0 and data.iva_porcentaje > 0:
        divisor = 1 + (data.iva_porcentaje / 100)
        gross_total = round(data.total + withholding, 2) if withholding > 0 else data.total
        inferred_base = round(gross_total / divisor, 2)
        candidates.append((inferred_base, round(gross_total - inferred_base, 2)))

    filtered_candidates: list[tuple[float, float]] = []
    seen = set()
    for base_candidate, iva_candidate in candidates:
        if base_candidate <= 0 and iva_candidate <= 0:
            continue
        key = (round(base_candidate, 2), round(iva_candidate, 2))
        if key in seen:
            continue
        seen.add(key)
        filtered_candidates.append(key)

    if not filtered_candidates:
        return None

    def score_candidate(base_candidate: float, iva_candidate: float) -> tuple[int, int, float]:
        score = 0

        candidate_total = round(base_candidate + iva_candidate - withholding, 2)

        if data.total > 0 and abs(candidate_total - data.total) <= 0.02:
            score += 4
        elif data.total > 0 and abs(candidate_total - data.total) <= max(0.1, data.total * 0.02):
            score += 2

        if data.iva_porcentaje > 0:
            expected_iva = round(base_candidate * data.iva_porcentaje / 100, 2)
            if abs(expected_iva - iva_candidate) <= 0.02:
                score += 3
            elif abs(expected_iva - iva_candidate) <= max(0.1, expected_iva * 0.03):
                score += 1

        if line_sum > 0 and abs(base_candidate - line_sum) <= 0.02:
            score += 2
        elif line_sum > 0 and abs(base_candidate - line_sum) <= max(0.1, line_sum * 0.02):
            score += 1

        if iva_candidate > 0:
            score += 1

        total_distance = 0.0
        if data.total > 0:
            total_distance += abs(candidate_total - data.total)
        if data.iva_porcentaje > 0:
            total_distance += abs(round(base_candidate * data.iva_porcentaje / 100, 2) - iva_candidate)
        if line_sum > 0:
            total_distance += abs(base_candidate - line_sum)

        return score, int(abs(base_candidate - line_sum) <= 0.02), -round(total_distance, 4)

    best_base, best_iva = max(filtered_candidates, key=lambda candidate: score_candidate(*candidate))
    return round(best_base, 2), round(best_iva, 2)
