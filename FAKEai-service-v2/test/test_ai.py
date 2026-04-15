"""Test AI layer with Ollama + qwen2.5:3b on a few real invoices."""
import os, sys, asyncio, time

# Force AI enabled to test position-based + AI corrections
os.environ["DOC_AI_ENABLED"] = "true"

sys.path.insert(0, "/tmp/v2test")

from app.config import Settings
from app.pipeline.orchestrator import extract

settings = Settings()

COMPANY = {
    "name": "DISOFT SERVICIOS INFORMATICOS SL",
    "tax_id": "B76099134",
    "tax_ids": ["B76099134", "B35222249"],
}

SEP = "=" * 60

test_files = [
    ("88944c32-edcc-4227-83a3-c681e08ad51f.pdf", "application/pdf",   "Rectificativa Florbric"),
    ("0d748d6a-04a9-457f-b606-25e7e34e2fcc.jpeg", "image/jpeg",      "Carmelo Torres musico"),
    ("14c032e7-6807-434e-8e5e-beae8ca20822.jpeg", "image/jpeg",      "Olivetti tintas"),
    ("e6c5118e-bf6e-4bee-9279-39511d1aced6.jpeg", "image/jpeg",      "ESP Consultoria RGPD"),
    ("f3280996-b498-465c-85cd-d9d7fe796124.jpeg", "image/jpeg",      "Microdisk destructora"),
]

async def run():
    for fname, mime, label in test_files:
        path = "/app/storage/uploads/" + fname
        print(SEP)
        print("FILE:", label, f"({fname[:8]})")
        print(SEP)
        t0 = time.time()
        try:
            result = await extract(
                path, mime,
                company_name=COMPANY["name"],
                company_tax_id=COMPANY["tax_id"],
                company_tax_ids=COMPANY["tax_ids"],
                settings=settings,
            )
            elapsed = round(time.time() - t0, 1)
            d = result.data
            print(f"  Method: {result.method} | Provider: {result.provider} | {elapsed}s")
            print(f"  Confidence: {d.confianza:.2f}")
            print(f"  Invoice#: {d.numero_factura} | Date: {d.fecha}")
            print(f"  Proveedor: {d.proveedor} ({d.cif_proveedor})")
            print(f"  Cliente: {d.cliente} ({d.cif_cliente})")
            print(f"  Side: {d.operation_side}")
            print(f"  Base: {d.base_imponible} | Tax%: {d.iva_porcentaje} | Tax: {d.iva} | Total: {d.total}")
            print(f"  Lines: {len(d.lineas)}")
            for item in d.lineas[:2]:
                print(f"    - {item.descripcion[:45]}  amt={item.importe}")
            if result.warnings:
                print(f"  Warnings: {result.warnings}")
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()
        print()

asyncio.run(run())
