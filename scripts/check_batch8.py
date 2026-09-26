import json
from pathlib import Path

WORKING_DIR = Path(r"C:\Research-Knowledge-Base\rag_storage")
BATCH_DEF_PATH = WORKING_DIR / "batch_definitions.json"

with open(BATCH_DEF_PATH, "r", encoding="utf-8") as f:
    b_def = json.load(f)

print("Batch 8 items:")
for item in b_def.get("8", []):
    print(" -", item)
