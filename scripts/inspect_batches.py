import json
from pathlib import Path

WORKING_DIR = Path(r"C:\Research-Knowledge-Base\rag_storage")
BATCH_DEF_PATH = WORKING_DIR / "batch_definitions.json"
BATCH_PROG_PATH = WORKING_DIR / "batch_progress.json"
DOC_STATUS_PATH = WORKING_DIR / "kv_store_doc_status.json"

with open(BATCH_DEF_PATH, "r", encoding="utf-8") as f:
    b_def = json.load(f)

with open(DOC_STATUS_PATH, "r", encoding="utf-8") as f:
    doc_status = json.load(f)

print("Batch definitions keys:", b_def.keys())
total_in_batches = 0
all_batch_files = []
for k, v in b_def.items():
    print(f"Batch {k}: {len(v)} items")
    total_in_batches += len(v)
    all_batch_files.extend(v)

print(f"Total documents defined across all batches: {total_in_batches}")

# Let's see unique files in batches
unique_batch_files = set(all_batch_files)
print(f"Unique files in batch_definitions: {len(unique_batch_files)}")

# Check doc_status files
doc_status_files = {}
for doc_id, data in doc_status.items():
    fp = data.get("file_path") or data.get("metadata", {}).get("source_file")
    doc_status_files[fp] = (doc_id, data.get("status"))

print(f"Files represented in doc_status: {len(doc_status_files)}")

# Compare batch_files vs doc_status
in_batches_not_in_status = unique_batch_files - set(doc_status_files.keys())
print(f"\nIn batches but NOT in doc_status ({len(in_batches_not_in_status)}):")
for f in sorted(in_batches_not_in_status):
    print(" ", f)

in_status_not_in_batches = set(doc_status_files.keys()) - unique_batch_files
print(f"\nIn doc_status but NOT in batches ({len(in_status_not_in_batches)}):")
for f in sorted(in_status_not_in_batches):
    print(" ", f)
