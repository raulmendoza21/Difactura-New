from __future__ import annotations

from app.models.document_bundle import DocumentBundle
from app.models.extraction_result import ProcessingTraceItem


def build_processing_trace(
    *,
    bundle: DocumentBundle,
    input_kind: str,
    provider: str,
    method: str,
    used_ocr: bool,
    used_ai: bool,
    page_count: int,
) -> list[ProcessingTraceItem]:
    trace = [
        ProcessingTraceItem(
            stage="input_router",
            summary=f"Entrada clasificada como {input_kind or 'desconocida'} con {page_count} pagina(s).",
            engine="document_loader",
        ),
        ProcessingTraceItem(
            stage="text_geometry",
            summary=f"Bundle documental construido con {len(bundle.spans)} spans y {len(bundle.regions)} regiones.",
            engine="ocr/pdf",
        ),
        ProcessingTraceItem(
            stage="layout_analysis",
            summary="Se reconstruyo el orden de lectura y las regiones principales del documento.",
            engine="layout_analyzer",
        ),
        ProcessingTraceItem(
            stage="candidate_resolution",
            summary="Se compararon candidatos heuristicos, layout-aware y opcionalmente doc_ai para resolver el documento final.",
            engine="document_intelligence",
        ),
    ]
    if used_ocr:
        trace.append(
            ProcessingTraceItem(
                stage="ocr",
                summary="Se utilizo OCR con geometria para enriquecer la evidencia documental.",
                engine="paddleocr+tesseract",
            )
        )
    if used_ai:
        trace.append(
            ProcessingTraceItem(
                stage="doc_ai",
                summary="Se consulto el proveedor Doc AI como fuente secundaria de estructuracion.",
                engine=provider or method,
            )
        )
    return trace
