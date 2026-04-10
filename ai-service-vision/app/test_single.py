"""Quick single invoice test."""
import asyncio
import traceback
from app.vision_engine import extract_invoice
from app.config import Settings


async def main():
    s = Settings()
    ctx = {"name": "DISOFT SERVICIOS INFORMATICOS SL", "tax_id": "B76099134"}
    print(f"Model: {s.openai_model}")
    path = "/app/storage/uploads/6e9d894e-ecf8-4501-bd60-5d41c2ba1a15.jpeg"
    print("Testing invoice 6...")
    try:
        r = await extract_invoice(path, settings=s, company_context=ctx)
        d = r["data"]
        print(f"OK: num={d['numero_factura']}, base={d['base_imponible']}, total={d['total_factura']}, time={r['elapsed_seconds']:.1f}s")
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
