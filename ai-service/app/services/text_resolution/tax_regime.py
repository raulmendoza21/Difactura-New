from __future__ import annotations

from app.models.document_contract import TaxRegime
from app.models.invoice_model import InvoiceData


class TaxRegimeService:
    _IGIC_RATES = {0, 1, 3, 5, 7, 9.5, 15, 20}
    _IVA_RATES = {4, 10, 21}

    def resolve(self, *, raw_text: str, invoice: InvoiceData, document_type: str) -> tuple[TaxRegime, list[str]]:
        upper_text = (raw_text or "").upper()
        tax_rate = round(abs(float(invoice.iva_porcentaje or 0)), 2)

        if "AIEM" in upper_text:
            return "AIEM", ["tax_regime:AIEM"]
        if "NO SUJET" in upper_text:
            return "NOT_SUBJECT", ["tax_regime:not_subject"]
        if "EXENT" in upper_text:
            return "EXEMPT", ["tax_regime:exempt"]
        if "INVERSI" in upper_text and "SUJETO PASIVO" in upper_text:
            return "REVERSE_CHARGE", ["tax_regime:reverse_charge"]
        if tax_rate in self._IGIC_RATES:
            return "IGIC", [f"tax_regime:igic_rate:{tax_rate}"]
        if tax_rate in self._IVA_RATES:
            return "IVA", [f"tax_regime:iva_rate:{tax_rate}"]
        if "IGIC" in upper_text:
            return "IGIC", ["tax_regime:igic_keyword"]
        if "IVA" in upper_text:
            return "IVA", ["tax_regime:iva_keyword"]
        if document_type in {"ticket", "factura_simplificada"} and abs(invoice.base_imponible) > 0 and abs(invoice.iva) > 0:
            inferred_rate = round(abs(invoice.iva) / abs(invoice.base_imponible) * 100, 2)
            if inferred_rate in self._IGIC_RATES:
                return "IGIC", [f"tax_regime:igic_inferred:{inferred_rate}"]
            if inferred_rate in self._IVA_RATES:
                return "IVA", [f"tax_regime:iva_inferred:{inferred_rate}"]
        return "UNKNOWN", ["tax_regime:unknown"]


tax_regime_service = TaxRegimeService()
