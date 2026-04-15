import sys
sys.path.insert(0, "/tmp/v2test")
from app.loading.mistral_ocr import extract_text, is_available
print("available:", is_available())
t = extract_text("/app/storage/uploads/0d748d6a-04a9-457f-b606-25e7e34e2fcc.jpeg")
print(f"OK: {len(t)} chars")
print(t[:200])
