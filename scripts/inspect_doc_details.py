import json
from pathlib import Path

WORKING_DIR = Path(r"C:\Research-Knowledge-Base\rag_storage")
DOC_STATUS_PATH = WORKING_DIR / "kv_store_doc_status.json"
BATCH_DEF_PATH = WORKING_DIR / "batch_definitions.json"
BATCH_PROG_PATH = WORKING_DIR / "batch_progress.json"

with open(DOC_STATUS_PATH, "r", encoding="utf-8") as f:
    doc_status = json.load(f)

print(f"Total doc status entries: {len(doc_status)}")

# Let's inspect the fields in doc_status
sample_id = list(doc_status.keys())[0]
print(f"Sample doc status entry ({sample_id}):")
print(json.dumps(doc_status[sample_id], indent=2))

status_by_doc = {}
for k, v in doc_status.items():
    st = v.get("status", "unknown")
    status_by_doc.setdefault(st, []).append((k, v.get("file_path", v.get("content_summary", "unknown"))))

print("\nCounts:")
for st, lst in status_by_doc.items():
    print(f"  {st}: {len(lst)}")

if BATCH_DEF_PATH.exists():
    with open(BATCH_DEF_PATH, "r", encoding="utf-8") as f:
        b_def = json.load(f)
    print(f"\nBatch definitions keys: {list(b_def.keys()) if isinstance(b_def, dict) else len(b_def)}")
    if isinstance(b_def, list):
        print(f"Batch definitions list length: {len(b_def)}")
        if len(b_def) > 0:
            print("First item:", b_def[0])

if BATCH_PROG_PATH.exists():
    with open(BATCH_PROG_PATH, "r", encoding="utf-8") as f:
        b_prog = json.load(f)
    print(f"\nBatch progress keys: {list(b_prog.keys()) if isinstance(b_prog, dict) else len(b_prog)}")
