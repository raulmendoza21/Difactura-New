from __future__ import annotations

import re

from app.models.invoice_model import InvoiceData


class CompanyMatchingService:
    _LEGAL_TOKENS = {
        "SL",
        "SA",
        "SLU",
        "SC",
        "CB",
        "SRL",
        "SOCIEDAD",
        "LIMITADA",
        "ANONIMA",
        "PROFESIONAL",
    }
    _BLOCKED_PARTY_TOKENS = {
        "CLIENTE",
        "EMISOR",
        "PROVEEDOR",
        "DESTINATARIO",
        "COMPRADOR",
        "FACTURA",
        "TOTAL",
        "SUBTOTAL",
        "BASE",
        "IGIC",
        "IVA",
    }

    def normalize_company_context(self, company_context: dict[str, str] | None) -> dict[str, str]:
        company_context = company_context or {}
        return {
            "name": self.normalize_party_name(company_context.get("name", "")),
            "tax_id": self.clean_tax_id(company_context.get("tax_id", "") or company_context.get("taxId", "")),
        }

    def build_company_match(
        self,
        *,
        invoice: InvoiceData,
        company_context: dict[str, str] | None = None,
        preferred_match: dict[str, object] | None = None,
    ) -> tuple[dict[str, object], list[str]]:
        if preferred_match:
            return preferred_match, ["company_match:provided"]

        company = self.normalize_company_context(company_context)
        if not company["name"] and not company["tax_id"]:
            return {
                "issuer_matches_company": False,
                "recipient_matches_company": False,
                "matched_role": "",
                "matched_by": "",
                "confidence": 0.0,
            }, ["company_match:empty_context"]

        issuer_score, issuer_by = self.score_party_match(
            name=invoice.proveedor,
            tax_id=invoice.cif_proveedor,
            company_context=company,
        )
        recipient_score, recipient_by = self.score_party_match(
            name=invoice.cliente,
            tax_id=invoice.cif_cliente,
            company_context=company,
        )

        issuer_matches = issuer_score >= 55
        recipient_matches = recipient_score >= 55

        if issuer_matches and recipient_matches:
            if abs(issuer_score - recipient_score) >= 20:
                matched_role = "issuer" if issuer_score > recipient_score else "recipient"
            else:
                matched_role = "ambiguous"
        elif issuer_matches:
            matched_role = "issuer"
        elif recipient_matches:
            matched_role = "recipient"
        else:
            matched_role = ""

        matched_by = ""
        selected_score = 0
        if matched_role == "issuer":
            matched_by = issuer_by
            selected_score = issuer_score
        elif matched_role == "recipient":
            matched_by = recipient_by
            selected_score = recipient_score

        confidence = 0.0
        if matched_role == "ambiguous":
            confidence = round(max(issuer_score, recipient_score) / 150, 2)
        elif matched_role:
            confidence = round(selected_score / 100, 2)

        return {
            "issuer_matches_company": issuer_matches,
            "recipient_matches_company": recipient_matches,
            "matched_role": matched_role,
            "matched_by": matched_by,
            "confidence": confidence,
        }, [
            f"company_match:issuer_score={issuer_score}:{issuer_by or 'none'}",
            f"company_match:recipient_score={recipient_score}:{recipient_by or 'none'}",
            f"company_match:matched_role={matched_role or 'none'}",
        ]

    def matches_company_context(self, name: str, tax_id: str, company_context: dict[str, str] | None) -> bool:
        score, _ = self.score_party_match(
            name=name,
            tax_id=tax_id,
            company_context=self.normalize_company_context(company_context),
        )
        return score >= 55

    def score_party_match(self, *, name: str, tax_id: str, company_context: dict[str, str]) -> tuple[int, str]:
        company_tax_id = company_context.get("tax_id", "")
        company_name = company_context.get("name", "")
        cleaned_tax_id = self.clean_tax_id(tax_id)

        if company_tax_id and cleaned_tax_id and cleaned_tax_id == company_tax_id:
            return 100, "tax_id"

        normalized_name = self.normalize_party_name(name)
        if not normalized_name or not company_name:
            return 0, ""

        left = self.normalize_party_value(normalized_name)
        right = self.normalize_party_value(company_name)
        if left and right and left == right:
            return 85, "name_exact"

        left_tokens = self.meaningful_name_tokens(normalized_name)
        right_tokens = self.meaningful_name_tokens(company_name)
        overlap = left_tokens & right_tokens
        if len(overlap) >= 2:
            return 70, "name_overlap"
        if len(overlap) == 1:
            overlap_token = next(iter(overlap))
            if len(overlap_token) >= 6 and (len(left_tokens) <= 2 or len(right_tokens) <= 2):
                return 62, "name_single_overlap"

        anchor = self.company_anchor_token(company_name)
        if anchor and len(anchor) >= 6 and anchor in left:
            return 60, "name_anchor"
        return 0, ""

    def meaningful_name_tokens(self, value: str) -> set[str]:
        raw_tokens = [
            re.sub(r"[^A-Z0-9]", "", token)
            for token in re.findall(r"[A-Z0-9]+", (value or "").upper())
        ]
        filtered = {
            token
            for token in raw_tokens
            if len(token) >= 4 and token not in self._LEGAL_TOKENS and not token.isdigit()
        }
        if filtered:
            return filtered
        return {
            token
            for token in raw_tokens
            if len(token) >= 4 and token not in self._BLOCKED_PARTY_TOKENS and not token.isdigit()
        }

    def normalize_party_name(self, value: str) -> str:
        cleaned = re.sub(r"\s+", " ", (value or "").strip()).strip(" .,:;-")
        if not cleaned:
            return ""

        normalized_token = re.sub(r"[^A-Z0-9]", "", cleaned.upper())
        if normalized_token in self._BLOCKED_PARTY_TOKENS:
            return ""

        letters = sum(char.isalpha() for char in cleaned)
        digits = sum(char.isdigit() for char in cleaned)
        if letters < 3 or digits > max(3, letters):
            return ""
        return cleaned[:200]

    def normalize_party_value(self, value: str) -> str:
        return re.sub(r"[^A-Z0-9]", "", (value or "").upper())

    def company_anchor_token(self, value: str) -> str:
        meaningful = sorted(self.meaningful_name_tokens(value), key=len, reverse=True)
        return meaningful[0] if meaningful else ""

    def clean_tax_id(self, value: str) -> str:
        if not value:
            return ""
        cleaned = re.sub(r"[\s.\-]", "", value.upper())
        return cleaned.replace("|", "I")


company_matching_service = CompanyMatchingService()
