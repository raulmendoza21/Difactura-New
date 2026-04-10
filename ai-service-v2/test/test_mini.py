import sys, os
sys.path.insert(0, "/tmp/v2test")
from app.loading.loader import load_document
from app.discovery.field_scanner import scan
from app.resolvers import identity as id_r, parties as party_r, amounts as amt_r
from app.resolvers import line_items as li_r, operation as op_r

SEP = "=" * 60

# Quick test — only 3 files
test_files = [
    ("88944c32-edcc-4227-83a3-c681e08ad51f.pdf", "application/pdf"),
    ("0d748d6a-04a9-457f-b606-25e7e34e2fcc.jpeg", "image/jpeg"),
    ("1ac0d2c1-661b-45b2-87bb-43f4a3397a47.jpeg", "image/jpeg"),
    ("14c032e7-6807-434e-8e5e-beae8ca20822.jpeg", "image/jpeg"),
    ("21ff47a5-5b14-4116-a2ac-9a1d5652703a.jpeg", "image/jpeg"),
    ("9da53a25-7d92-48cf-a689-788156cc4027.jpeg", "image/jpeg"),
    ("e6c5118e-bf6e-4bee-9279-39511d1aced6.jpeg", "image/jpeg"),
    ("f3280996-b498-465c-85cd-d9d7fe796124.jpeg", "image/jpeg"),
    ("42162d11-6470-4697-b53c-9e2bd3ca01f2.jpeg", "image/jpeg"),
    ("abf77f0e-3c95-4402-8571-23a55475a7c8.jpeg", "image/jpeg"),
    ("c3bea985-7939-4e12-942b-b71d643b2bdc.jpeg", "image/jpeg"),
    ("dad41b07-c4fa-42e0-b63f-15c52910d4b8.jpeg", "image/jpeg"),
]

for fname, mime in test_files:
    path = "/app/storage/uploads/" + fname
    print(SEP)
    print("FILE:", fname)
    print(SEP)
    try:
        doc = load_document(path, mime)
        text = doc["text"]
        src = doc["source"]
        print("  Text: %d chars | source: %s" % (len(text), src))
        if not text.strip():
            print("  *** EMPTY ***")
            continue
        print("  Preview:", text[:200])
        print()
        sr = scan(text)
        print("  Fields: %d | TaxIDs: %d | Amounts: %d" % (len(sr.fields), len(sr.tax_ids), len(sr.amounts)))

        idn = id_r.resolve(sr)
        print("  Invoice#:", idn["numero_factura"], "| Date:", idn["fecha"])

        pty = party_r.resolve(sr)
        print("  Entities:", len(pty["entities"]))
        for e in pty["entities"]:
            name = e["nombre"][:50] if e["nombre"] else ""
            print("    - CIF: %s  Name: %s" % (e["cif"], name))

        money = amt_r.resolve(sr)
        print("  Base:", money.get("base_imponible"), "| Tax%:", money.get("iva_porcentaje"), "| Tax:", money.get("iva"), "| Total:", money.get("total"))

        li = li_r.resolve(sr, money.get("base_imponible"))
        print("  Lines:", len(li["lineas"]))
        for item in li["lineas"][:2]:
            print("    -", item.descripcion[:40], " amt=", item.importe)

        ops = op_r.resolve(sr, iva_porcentaje=money.get("iva_porcentaje"))
        print("  Type:", ops["tipo_factura"], "| Regime:", ops["tax_regime"])
    except Exception as e:
        print("  ERROR:", e)
        import traceback
        traceback.print_exc()
    print()
