import sys, os
sys.path.insert(0, "/tmp/v2test")
from app.loading.loader import load_document
from app.discovery.field_scanner import scan
from app.resolvers import identity as id_r, parties as party_r, amounts as amt_r
from app.resolvers import line_items as li_r, operation as op_r

SEP = "=" * 70
upload_dir = "/app/storage/uploads"
files = sorted([f for f in os.listdir(upload_dir) if not f.startswith(".")])
print(f"Found {len(files)} uploads\n")

# DISOFT is a Canarian company using IGIC — has two known CIFs
company_ctx = {"name": "DISOFT SERVICIOS INFORMATICOS SL", "tax_id": "B76099134", "tax_ids": ["B76099134", "B35222249"]}

for f in files:
    ext = os.path.splitext(f)[1].lower()
    if ext in (".jpeg", ".jpg"):
        mime = "image/jpeg"
    elif ext == ".png":
        mime = "image/png"
    elif ext == ".pdf":
        mime = "application/pdf"
    else:
        continue

    path = os.path.join(upload_dir, f)
    print(SEP)
    print(f"FILE: {f}")
    print(SEP)
    try:
        doc = load_document(path, mime)
        text = doc["text"]
        print(f"  Text: {len(text)} chars | source: {doc['source']} | pages: {doc['pages']}")
        if not text.strip():
            print("  *** EMPTY ***\n")
            continue
        print(f"  Preview: {text[:300]}\n")

        sr = scan(text)
        print(f"  Discovered: {len(sr.fields)} fields, {len(sr.tax_ids)} tax_ids, {len(sr.amounts)} amounts")

        idn = id_r.resolve(sr)
        print(f"  Invoice#: {idn['numero_factura']} | Date: {idn['fecha']}")
        if idn["rectified_invoice_number"]:
            print(f"  Rectified: {idn['rectified_invoice_number']}")

        pty = party_r.resolve(sr)
        print(f"  Entities found: {len(pty['entities'])}")
        for ent in pty["entities"]:
            print(f"    - CIF: {ent['cif']}  Name: {ent['nombre'][:60]}")

        money = amt_r.resolve(sr)
        print(f"  Base: {money.get('base_imponible')} | Tax%: {money.get('iva_porcentaje')} | Tax: {money.get('iva')} | Total: {money.get('total')}")
        if money.get("retencion"):
            print(f"  Ret%: {money.get('retencion_porcentaje')} | Ret: {money.get('retencion')}")

        li = li_r.resolve(sr, money.get("base_imponible"))
        print(f"  LineItems: {len(li['lineas'])}")
        for item in li["lineas"][:3]:
            print(f"    - {item.descripcion[:50]}  amt={item.importe}")

        ops = op_r.resolve(sr, iva_porcentaje=money.get("iva_porcentaje"))
        print(f"  Type: {ops['tipo_factura']} | Regime: {ops['tax_regime']}")
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
    print()
