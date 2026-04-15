"""Batch test: compare OpenAI gpt-4.1-nano vs old Ollama results."""
import asyncio
import json

from app.pipeline.orchestrator import extract
from app.config import settings

INVOICES = [
    (53, "/app/storage/uploads/43e92679-081b-457e-b040-3fb8b8b7ffd8.jpeg", "image/jpeg", "No7", 0.0),
    (33, "/app/storage/uploads/f59033c2-0076-457e-ace3-8270570a5323.jpeg", "image/jpeg", "", 0.05),
    (40, "/app/storage/uploads/dad41b07-c4fa-42e0-b63f-15c52910d4b8.jpeg", "image/jpeg", "", 0.05),
    (25, "/app/storage/uploads/d2e20058-4db8-4b7a-ae3c-231c02191451.jpeg", "image/jpeg", "", 0.65),
    (41, "/app/storage/uploads/21ff47a5-5b14-4116-a2ac-9a1d5652703a.jpeg", "image/jpeg", "", 0.66),
    (9,  "/app/storage/uploads/88944c32-edcc-4227-83a3-c681e08ad51f.pdf", "application/pdf", "AB202600002", 0.66),
    (7,  "/app/storage/uploads/1a781081-6835-4a5f-8659-aa5fdfb12990.jpeg", "image/jpeg", "AB202600002", 0.68),
    (31, "/app/storage/uploads/10c80fad-0858-4334-ab99-18c7d07b3a3e.jpeg", "image/jpeg", "", 0.68),
    (11, "/app/storage/uploads/9da53a25-7d92-48cf-a689-788156cc4027.jpeg", "image/jpeg", "", 0.68),
    (44, "/app/storage/uploads/abf77f0e-3c95-4402-8571-23a55475a7c8.jpeg", "image/jpeg", "", 0.69),
]


async def main():
    header = f"{'ID':>3} | {'OLD':>5} | {'NEW':>5} | {'D':>5} | {'OLD_NUM':>15} | {'NEW_NUM':>15} | {'PROVEEDOR':>28} | METHOD"
    print(header)
    print("-" * len(header))

    total_old = 0.0
    total_new = 0.0
    improved = 0
    same = 0
    worse = 0

    for fid, path, mime, old_num, old_conf in INVOICES:
        try:
            r = await extract(
                path, mime,
                company_name="DISOFT SERVICIOS INFORMATICOS SL",
                company_tax_id="B76099134",
                company_tax_ids=["B76099134", "B35222249"],
                settings=settings,
            )
            d = r.data.model_dump()
            nc = d["confianza"]
            delta = nc - old_conf
            sign = "+" if delta > 0 else ""
            nn = str(d["numero_factura"] or "")[:15]
            prov = str(d["proveedor"] or "")[:28]

            print(f"{fid:>3} | {old_conf:>5.2f} | {nc:>5.2f} | {sign}{delta:>4.2f} | {str(old_num):>15} | {nn:>15} | {prov:>28} | {r.method}")

            total_old += old_conf
            total_new += nc
            if nc > old_conf + 0.01:
                improved += 1
            elif nc < old_conf - 0.01:
                worse += 1
            else:
                same += 1
        except Exception as e:
            print(f"{fid:>3} | ERROR: {e}")

    n = len(INVOICES)
    print("-" * len(header))
    print(f"AVG:  {total_old/n:.2f} -> {total_new/n:.2f}  |  improved={improved}  same={same}  worse={worse}")


asyncio.run(main())
