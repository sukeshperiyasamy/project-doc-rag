import os
import json
from pathlib import Path

BASE_DIR = Path(r"C:\Research-Knowledge-Base")
RAG_DIR = BASE_DIR / "rag_storage"
SOURCE_DIR = Path(r"C:\Users\sukes\Downloads\mtp")

with open(RAG_DIR / "kv_store_doc_status.json", "r", encoding="utf-8") as f:
    doc_status = json.load(f)

with open(RAG_DIR / "batch_definitions.json", "r", encoding="utf-8") as f:
    batch_defs = json.load(f)

with open(RAG_DIR / "kv_store_full_docs.json", "r", encoding="utf-8") as f:
    full_docs = json.load(f)

with open(RAG_DIR / "kv_store_text_chunks.json", "r", encoding="utf-8") as f:
    text_chunks = json.load(f)

# Build map of doc_status by file_path
doc_by_filename = {}
for doc_id, info in doc_status.items():
    fp = info.get("file_path", "")
    fname = Path(fp).name
    doc_by_filename[fname] = (doc_id, info)

processed_files = []
failed_files = []
stuck_files = []
batch8_files = []
excel_files = []
other_supported = []

EXCLUDED_EXT = {".xlsx", ".xls"}
SUPPORTED_EXT = {".docx", ".pdf", ".csv", ".txt", ".md", ".pptx"}

batch8_set = set(batch_defs.get("8", []))

source_files = sorted(list(SOURCE_DIR.iterdir()), key=lambda x: x.name)

for sf in source_files:
    if not sf.is_file():
        continue
    name = sf.name
    ext = sf.suffix.lower()

    if ext in EXCLUDED_EXT:
        excel_files.append(name)
        continue

    if ext not in SUPPORTED_EXT:
        continue

    # Check doc_status
    if name in doc_by_filename:
        doc_id, info = doc_by_filename[name]
        st = info.get("status")
        if st == "processed":
            processed_files.append((name, doc_id))
        elif st == "failed":
            failed_files.append((name, doc_id))
        elif st == "processing":
            stuck_files.append((name, doc_id))
        else:
            other_supported.append((name, doc_id, st))
    else:
        # Check if in batch 8
        if name in batch8_set:
            batch8_files.append(name)
        else:
            other_supported.append((name, None, "UNREGISTERED"))

print("=== RECONCILIATION REPORT ===")
print(f"Total Source Supported Files: {len(processed_files) + len(failed_files) + len(stuck_files) + len(batch8_files) + len(other_supported)}")
print(f"1. Already PROCESSED (MUST NOT TOUCH): {len(processed_files)}")
print(f"2. FAILED (Need local ingestion):     {len(failed_files)}")
print(f"3. STUCK (NAM_Capture_Strategies.md):  {len(stuck_files)}")
print(f"4. BATCH 8 Unregistered:              {len(batch8_files)}")
print(f"5. Other Unregistered/Other Status:   {len(other_supported)}")
print(f"6. EXCLUDED Excel (.xlsx):            {len(excel_files)}")

print("\n--- Details of STUCK files ---")
for fn, did in stuck_files:
    print(f"  * {fn} (id: {did})")

print("\n--- Details of BATCH 8 files ---")
for fn in batch8_files:
    print(f"  * {fn}")

print("\n--- Details of Other files ---")
for fn, did, st in other_supported:
    print(f"  * {fn} (id: {did}, status: {st})")

print("\n--- Details of EXCLUDED Excel files ---")
for fn in excel_files:
    print(f"  * {fn}")
