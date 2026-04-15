import sys
sys.path.insert(0, "/tmp/v2test")
from app.loading.loader import load_document

files = [
    ("14c032e7-6807-434e-8e5e-beae8ca20822.jpeg", "image/jpeg"),
    ("21ff47a5-5b14-4116-a2ac-9a1d5652703a.jpeg", "image/jpeg"),
    ("3f0e4ab3-e1dd-480e-88e5-15e5e72e0054.jpeg", "image/jpeg"),
    ("7f13b1d1-dec3-4b3e-a2b3-424b8e1e4cd8.jpeg", "image/jpeg"),
    ("b8da2aee-12e3-4fc2-96a2-f460b3f26fc3.jpeg", "image/jpeg"),
]
for fname, mime in files:
    doc = load_document("/app/storage/uploads/" + fname, mime)
    print("=== %s ===" % fname)
    for i, line in enumerate(doc["text"].split("\n")):
        print("%03d: %s" % (i, line))
    print()
