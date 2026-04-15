"""Dump OCR text around tax IDs for debugging name association."""
import os, sys, re
os.environ["DOC_AI_ENABLED"] = "true"
sys.path.insert(0, "/tmp/v2test")

from app.loading.loader import load_document
from app.discovery.field_scanner import scan
from app.utils.regex_lib import ANY_TAX_ID

files = [
    ("0d748d6a-04a9-457f-b606-25e7e34e2fcc.jpeg", "image/jpeg", "Carmelo Torres"),
    ("14c032e7-6807-434e-8e5e-beae8ca20822.jpeg", "image/jpeg", "Olivetti"),
]
for fname, mime, label in files:
    doc = load_document(f"/app/storage/uploads/{fname}", mime)
    lines = [l.strip() for l in doc["text"].split("\n") if l.strip()]
    print(f"\n{'='*50}\n{label}\n{'='*50}")
    for i, line in enumerate(lines):
        marker = ""
        if ANY_TAX_ID.search(line):
            marker = "  <-- CIF HERE"
        print(f"  [{i:3d}] {line}{marker}")
