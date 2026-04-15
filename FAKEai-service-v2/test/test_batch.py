"""Batch test — process all uploads in groups of N, print summary."""
import os, sys, asyncio, time, glob

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

MIME_MAP = {
    ".pdf": "application/pdf",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".tiff": "image/tiff",
}

BATCH_SIZE = 5
SEP = "=" * 60


def get_all_files():
    """Discover all processable files in uploads."""
    upload_dir = "/app/storage/uploads"
    files = []
    for f in sorted(os.listdir(upload_dir)):
        ext = os.path.splitext(f)[1].lower()
        if ext in MIME_MAP:
            files.append((os.path.join(upload_dir, f), MIME_MAP[ext], f))
    return files


async def process_one(path, mime, fname):
    """Process a single file, return summary dict."""
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
        return {
            "file": fname[:12],
            "ok": True,
            "time": elapsed,
            "method": result.method,
            "conf": round(d.confianza, 2),
            "inv": d.numero_factura or "-",
            "date": d.fecha or "-",
            "prov": f"{d.proveedor[:30]} ({d.cif_proveedor})" if d.proveedor or d.cif_proveedor else "-",
            "cli": f"{d.cliente[:30]} ({d.cif_cliente})" if d.cliente or d.cif_cliente else "-",
            "side": d.operation_side or "-",
            "base": d.base_imponible,
            "tax_pct": d.iva_porcentaje,
            "total": d.total,
            "lines": len(d.lineas),
            "warnings": result.warnings,
        }
    except Exception as e:
        elapsed = round(time.time() - t0, 1)
        return {"file": fname[:12], "ok": False, "time": elapsed, "error": str(e)}


async def run():
    files = get_all_files()
    total = len(files)
    batch_start = int(os.environ.get("BATCH_START", "0"))
    batch_end = min(batch_start + BATCH_SIZE, total)

    print(f"Total files: {total} | Processing batch: {batch_start+1}-{batch_end}")
    print(SEP)

    results = []
    for i in range(batch_start, batch_end):
        path, mime, fname = files[i]
        print(f"[{i+1}/{total}] {fname[:20]}...", end=" ", flush=True)
        r = await process_one(path, mime, fname)
        results.append(r)
        if r["ok"]:
            print(f"✓ {r['time']}s conf={r['conf']} side={r['side']} method={r['method']}")
        else:
            print(f"✗ {r['time']}s ERROR: {r['error'][:60]}")

    # Summary table
    print(f"\n{SEP}")
    print(f"BATCH {batch_start+1}-{batch_end} SUMMARY")
    print(SEP)

    ok_count = sum(1 for r in results if r["ok"])
    ai_count = sum(1 for r in results if r.get("method") == "heuristic+ai")
    sides = {"compra": 0, "venta": 0, "-": 0}
    conf_sum = 0

    for r in results:
        if not r["ok"]:
            print(f"  {r['file']}  ERROR: {r.get('error', '')[:50]}")
            continue
        sides[r["side"]] = sides.get(r["side"], 0) + 1
        conf_sum += r["conf"]
        mark = "AI" if "ai" in r.get("method", "") else "  "
        print(
            f"  {r['file']}  [{mark}] conf={r['conf']:.2f} "
            f"side={r['side']:6s} inv={r['inv'][:15]:15s} "
            f"base={r['base']:>8} total={r['total']:>8} "
            f"lines={r['lines']} "
            f"prov={r['prov'][:25]}"
        )
        if r.get("warnings"):
            for w in r["warnings"]:
                print(f"           ↳ {w}")

    print(SEP)
    avg_conf = round(conf_sum / ok_count, 2) if ok_count else 0
    print(f"OK: {ok_count}/{len(results)} | AI used: {ai_count} | Avg conf: {avg_conf}")
    print(f"Sides: compra={sides.get('compra',0)} venta={sides.get('venta',0)} unknown={sides.get('-',0)}")
    print(f"Next batch: BATCH_START={batch_end}")


asyncio.run(run())
