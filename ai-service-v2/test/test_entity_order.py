"""Check entity extraction order — first entity = emisor?"""
import os, sys
os.environ["DOC_AI_ENABLED"] = "true"
sys.path.insert(0, "/tmp/v2test")

from app.loading.loader import load_document
from app.discovery.field_scanner import scan
from app.resolvers import parties as pr

files = [
    ("0d748d6a-04a9-457f-b606-25e7e34e2fcc.jpeg", "image/jpeg", "Carmelo Torres"),
    ("14c032e7-6807-434e-8e5e-beae8ca20822.jpeg", "image/jpeg", "Olivetti"),
    ("f3280996-b498-465c-85cd-d9d7fe796124.jpeg", "image/jpeg", "Microdisk"),
    ("e6c5118e-bf6e-4bee-9279-39511d1aced6.jpeg", "image/jpeg", "ESP Consultoria"),
    ("88944c32-edcc-4227-83a3-c681e08ad51f.pdf", "application/pdf", "Rectificativa"),
]
for fname, mime, label in files:
    doc = load_document(f"/app/storage/uploads/{fname}", mime)
    sr = scan(doc["text"])
    p = pr.resolve(sr)
    print(f"{label}:")
    for i, e in enumerate(p["entities"]):
        print(f"  [{i}] {e['cif']} -> {e['nombre']}")
    print()
