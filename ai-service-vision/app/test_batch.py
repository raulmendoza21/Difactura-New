"""Batch test: vision engine on 9 invoices (easy + hard)."""
import asyncio
import json
from app.vision_engine import extract_invoice
from app.config import Settings

INVOICES = [
    (4,  "/app/storage/uploads/53588172-d311-446a-a595-dbbb431a522e.jpeg"),
    (6,  "/app/storage/uploads/6e9d894e-ecf8-4501-bd60-5d41c2ba1a15.jpeg"),
    (25, "/app/storage/uploads/d2e20058-4db8-4b7a-ae3c-231c02191451.jpeg"),
    (31, "/app/storage/uploads/10c80fad-0858-4334-ab99-18c7d07b3a3e.jpeg"),
    (33, "/app/storage/uploads/f59033c2-0076-457e-ace3-8270570a5323.jpeg"),
    (40, "/app/storage/uploads/dad41b07-c4fa-42e0-b63f-15c52910d4b8.jpeg"),
    (41, "/app/storage/uploads/21ff47a5-5b14-4116-a2ac-9a1d5652703a.jpeg"),
    (44, "/app/storage/uploads/abf77f0e-3c95-4402-8571-23a55475a7c8.jpeg"),
    (53, "/app/storage/uploads/43e92679-081b-457e-b040-3fb8b8b7ffd8.jpeg"),
]

# v2 engine results for comparison
V2_DATA = {
    4:  {"num": "GC 26001163",            "base": 25.00,    "iva": 7.0,   "total": 26.75,    "conf": 0.94},
    6:  {"num": "14/2025",                 "base": 15000.00, "iva": 7.0,   "total": 16050.00, "conf": 0.94},
    25: {"num": "2282",                    "base": 103.00,   "iva": 90.67, "total": 196.39,   "conf": 0.63},
    31: {"num": "",                        "base": 1393.59,  "iva": 7.0,   "total": 1491.14,  "conf": 0.68},
    33: {"num": "2025/00006884",           "base": 8.00,     "iva": 7.0,   "total": 8.52,     "conf": 0.92},
    40: {"num": "LM1159",                  "base": 129.00,   "iva": 3.0,   "total": 168.65,   "conf": 0.80},
    41: {"num": "COMPROBANTE 08/07/2025",  "base": 112.50,   "iva": 7.0,   "total": 120.50,   "conf": 0.75},
    44: {"num": "",                        "base": 86.59,    "iva": 5.0,   "total": 90.92,    "conf": 0.69},
    53: {"num": "No7",                     "base": 553.60,   "iva": 7.0,   "total": 592.35,   "conf": 0.91},
}


async def main():
    settings = Settings()
    ctx = {"name": "DISOFT SERVICIOS INFORMATICOS SL", "tax_id": "B76099134"}
    print(f"Model: {settings.openai_model}")
    print("=" * 120)
    header = f"{'ID':>3} | {'num_factura':25} | {'base':>10} | {'iva%':>6} | {'total':>10} | {'emisor':25} | {'t':>5} | {'tok':>5}"
    print(header)
    print("-" * 120)

    total_time = 0
    total_tokens = 0
    results = {}

    for fid, path in INVOICES:
        try:
            r = await extract_invoice(path, settings=settings, company_context=ctx)
            d = r["data"]
            results[fid] = d
            nf = (d["numero_factura"] or "")[:25]
            base = d["base_imponible"] or 0
            iva = d["iva_porcentaje"] or 0
            total = d["total_factura"] or 0
            emisor = (d["emisor_nombre"] or "")[:25]
            el = r["elapsed_seconds"]
            tok = r["usage"]["prompt_tokens"] + r["usage"]["completion_tokens"]
            total_time += el
            total_tokens += tok
            print(f"{fid:3} | {nf:25} | {base:10.2f} | {iva:6.1f} | {total:10.2f} | {emisor:25} | {el:5.1f}s | {tok:5}")
        except Exception as e:
            print(f"{fid:3} | ERROR: {e}")

    print("=" * 120)
    print(f"Total time: {total_time:.1f}s | Total tokens: {total_tokens}")
    print()

    # Comparison with v2 (using already-fetched results)
    print("\n=== COMPARISON: Vision vs v2 engine ===")
    print(f"{'ID':>3} | {'v2_num':20} | {'vis_num':20} | {'v2_base':>10} | {'vis_base':>10} | {'v2_iva%':>7} | {'vis_iva%':>7} | {'v2_total':>10} | {'vis_total':>10}")
    print("-" * 130)

    for fid, d in results.items():
        v2 = V2_DATA[fid]
        v2n = (v2["num"] or "")[:20]
        visn = (d["numero_factura"] or "")[:20]
        print(f"{fid:3} | {v2n:20} | {visn:20} | {v2['base']:10.2f} | {(d['base_imponible'] or 0):10.2f} | {v2['iva']:7.1f} | {(d['iva_porcentaje'] or 0):7.1f} | {v2['total']:10.2f} | {(d['total_factura'] or 0):10.2f}")


if __name__ == "__main__":
    asyncio.run(main())
