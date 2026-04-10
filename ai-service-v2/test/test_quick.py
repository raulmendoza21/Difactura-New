"""Quick smoke test — run extraction on a sample invoice."""
import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app.pipeline.orchestrator import extract


async def main():
    samples = [
        r"C:\Users\raule\Documents\DISOFT-NEW\samples\invoices\factura-realista-01.pdf",
        r"C:\Users\raule\Documents\DISOFT-NEW\samples\invoices-pack-02\factura-servicios-it-01.pdf",
        r"C:\Users\raule\Documents\DISOFT-NEW\samples\invoices-pack-02\factura-material-oficina-02.pdf",
    ]

    for path in samples:
        if not os.path.exists(path):
            print(f"SKIP (not found): {path}")
            continue

        print(f"\n{'='*70}")
        print(f"FILE: {os.path.basename(path)}")
        print(f"{'='*70}")

        try:
            result = await extract(
                file_path=path,
                mime_type="application/pdf",
                company_name="Mi Empresa SL",
                company_tax_id="B12345678",
            )
            payload = result.to_api_payload()
            # Print key fields
            for key in ["numero_factura", "fecha", "proveedor", "cif_proveedor",
                         "cliente", "cif_cliente", "base_imponible", "iva_porcentaje",
                         "iva", "total", "retencion_porcentaje", "retencion",
                         "tipo_factura", "confianza", "document_type", "tax_regime",
                         "method", "pages", "warnings"]:
                print(f"  {key}: {payload.get(key)}")
            if payload.get("lineas"):
                print(f"  lineas ({len(payload['lineas'])}):")
                for li in payload["lineas"][:5]:
                    print(f"    - {li['descripcion'][:50]}  qty={li['cantidad']}  amt={li['importe']}")
            print(f"  field_confidence: {json.dumps(payload.get('field_confidence', {}), indent=4)}")
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
