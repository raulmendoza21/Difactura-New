from __future__ import annotations

from app.models.invoice_model import InvoiceData
from app.services.text_resolution.amount_resolution_parts.candidate_selection import pick_best_amounts
from app.services.text_resolution.line_items import line_item_resolution_service


def normalize_amounts(data: InvoiceData) -> list[str]:
    warnings: list[str] = []
    line_sum = round(sum(line.importe for line in data.lineas if line.importe > 0), 2)
    withholding = round(max(0, data.retencion or 0), 2)

    if data.total > 0 and data.iva_porcentaje > 0 and data.base_imponible <= 0 and data.iva <= 0:
        divisor = 1 + (data.iva_porcentaje / 100)
        gross_total = round(data.total + withholding, 2) if withholding > 0 else data.total
        data.base_imponible = round(gross_total / divisor, 2)
        data.iva = round(gross_total - data.base_imponible, 2)
        warnings.append("base_e_iva_inferidos_desde_total_y_porcentaje")

    if data.total > 0 and data.base_imponible > 0 and data.iva <= 0:
        gross_total = round(data.total + withholding, 2) if withholding > 0 else data.total
        data.iva = round(max(0, gross_total - data.base_imponible), 2)
        warnings.append("iva_inferido_desde_total")

    if data.base_imponible > 0 and data.iva_porcentaje > 0:
        expected_iva = round(data.base_imponible * data.iva_porcentaje / 100, 2)
        if data.total > 0:
            expected_total = round(data.base_imponible + expected_iva - withholding, 2)
            current_diff = abs(round(data.base_imponible + data.iva - withholding, 2) - data.total)
            expected_diff = abs(expected_total - data.total)
            if expected_diff + 0.02 < current_diff:
                data.iva = expected_iva
                warnings.append("iva_recalculado_desde_porcentaje")
        elif data.iva <= 0 or abs(data.iva - expected_iva) > 0.02:
            data.iva = expected_iva
            warnings.append("iva_recalculado_desde_porcentaje")

    if data.base_imponible > 0 and data.iva > 0 and data.iva_porcentaje <= 0:
        data.iva_porcentaje = round((data.iva / data.base_imponible) * 100, 2)
        warnings.append("iva_porcentaje_inferido_desde_base_e_iva")

    if data.base_imponible > 0 and data.iva > 0 and data.total <= 0:
        data.total = round(data.base_imponible + data.iva - withholding, 2)
        warnings.append("total_inferido_desde_base_e_iva")

    if data.total > 0 and data.iva > 0 and data.base_imponible <= 0:
        gross_total = round(data.total + withholding, 2) if withholding > 0 else data.total
        data.base_imponible = round(max(0, gross_total - data.iva), 2)
        warnings.append("base_inferida_desde_total_e_iva")

    summary_is_consistent = (
        data.base_imponible > 0
        and data.total > 0
        and (data.iva <= 0 or abs(round(data.base_imponible + data.iva - withholding, 2) - data.total) <= 0.05)
    )
    summary_leak_suspected = line_item_resolution_service.has_summary_leak_pattern(
        data.lineas,
        base_amount=data.base_imponible,
        total_amount=data.total,
    )

    if line_sum > 0 and data.total > 0 and data.total + 0.02 < line_sum:
        if summary_is_consistent and summary_leak_suspected:
            warnings.append("lineas_inconsistentes_con_resumen_fiscal")
        else:
            data.base_imponible = line_sum
            if data.iva_porcentaje > 0:
                data.iva = round(line_sum * data.iva_porcentaje / 100, 2)
                data.total = round(data.base_imponible + data.iva - withholding, 2)
                warnings.append("total_reconstruido_desde_lineas")
            else:
                data.total = line_sum
                warnings.append("total_ajustado_al_minimo_de_lineas")

    if data.total > 0 and data.base_imponible > 0 and data.iva > 0:
        expected_total = round(data.base_imponible + data.iva - withholding, 2)
        if abs(expected_total - data.total) > 0.02:
            if line_sum > 0 and abs(line_sum - data.base_imponible) <= 0.02:
                data.total = expected_total
                warnings.append("total_recalculado_desde_base_e_iva")

    amount_candidates = pick_best_amounts(data, line_sum)
    if amount_candidates:
        base_candidate, iva_candidate = amount_candidates
        if line_sum > 0 and abs(base_candidate - line_sum) <= 0.02 and abs(data.base_imponible - base_candidate) > 0.02:
            warnings.append("base_reconciliada_con_lineas")
        elif abs(data.base_imponible - base_candidate) > 0.02:
            warnings.append("base_recalculada_por_consistencia")

        if abs(data.iva - iva_candidate) > 0.02:
            warnings.append("iva_recalculado_por_consistencia")

        data.base_imponible = base_candidate
        data.iva = iva_candidate

    return warnings
