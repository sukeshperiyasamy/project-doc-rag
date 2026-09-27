import os
import json
from pathlib import Path

BASE_DIR = Path(r"C:\Research-Knowledge-Base")
RAG_DIR = BASE_DIR / "rag_storage"
SOURCE_DIR = Path(r"C:\Users\sukes\Downloads\mtp")

# Load doc status from LightRAG storage
with open(RAG_DIR / "kv_store_doc_status.json", "r", encoding="utf-8") as f:
    doc_status = json.load(f)

# Load batch definitions if present
batch_defs = {}
if (RAG_DIR / "batch_definitions.json").exists():
    with open(RAG_DIR / "batch_definitions.json", "r", encoding="utf-8") as f:
        batch_defs = json.load(f)

# Load text chunks
with open(RAG_DIR / "kv_store_text_chunks.json", "r", encoding="utf-8") as f:
    text_chunks = json.load(f)

processed_docs = []
failed_docs = []
processing_docs = []
other_docs = []

for doc_id, info in doc_status.items():
    status = info.get("status")
    fname = info.get("file_path", doc_id)
    if status == "processed":
        processed_docs.append((doc_id, fname))
    elif status == "failed":
        failed_docs.append((doc_id, fname))
    elif status == "processing":
        processing_docs.append((doc_id, fname))
    else:
        other_docs.append((doc_id, fname, status))

print(f"=== LightRAG kv_store_doc_status Summary ===")
print(f"Total registered in kv_store_doc_status: {len(doc_status)}")
print(f"Processed: {len(processed_docs)}")
print(f"Failed: {len(failed_docs)}")
print(f"Processing (stuck): {len(processing_docs)}")
if processing_docs:
    for d, fn in processing_docs:
        print(f"  * Stuck: {fn} (id: {d})")
print(f"Other statuses: {len(other_docs)}")

# Source directory check
EXCLUDED_EXT = {".xlsx", ".xls"}
SUPPORTED_EXT = {".docx", ".pdf", ".csv", ".txt", ".md", ".pptx"}

source_files = list(SOURCE_DIR.iterdir())
source_supported = [f for f in source_files if f.is_file() and f.suffix.lower() in SUPPORTED_EXT and f.suffix.lower() not in EXCLUDED_EXT]
source_excel = [f for f in source_files if f.is_file() and f.suffix.lower() in EXCLUDED_EXT]

print(f"\n=== Source Directory (C:\\Users\\sukes\\Downloads\\mtp) ===")
print(f"Total files in source: {len(source_files)}")
print(f"Supported files (non-Excel): {len(source_supported)}")
print(f"Excel files (EXCLUDED): {len(source_excel)}")
for ef in source_excel:
    print(f"  * Excluded Excel: {ef.name}")

# Batch 8 inspection
batch8_files = batch_defs.get("batch_8", {}).get("files", []) if isinstance(batch_defs, dict) else []
print(f"\n=== Batch 8 Files ({len(batch8_files)} files) ===")
# Check which Batch 8 files are registered in doc_status
registered_filenames = {info.get("file_path", ""): doc_id for doc_id, info in doc_status.items()}
batch8_unregistered = []
for bf in batch8_files:
    # check if filename or basename matches
    b_name = Path(bf).name
    found = False
    for rfn in registered_filenames:
        if Path(rfn).name == b_name:
            found = True
            break
    if not found:
        batch8_unregistered.append(b_name)
    print(f"  * {b_name:<55} Registered: {found}")

print(f"Total Batch 8 Unregistered: {len(batch8_unregistered)}")

# Chunks breakdown
chunks_by_doc = {}
for ch_id, ch_data in text_chunks.items():
    doc_id = ch_data.get("full_doc_id")
    chunks_by_doc.setdefault(doc_id, []).append(ch_id)

failed_doc_ids = {d[0] for d in failed_docs}
processing_doc_ids = {d[0] for d in processing_docs}
processed_doc_ids = {d[0] for d in processed_docs}

chunks_for_processed = sum(len(chunks_by_doc.get(did, [])) for did in processed_doc_ids)
chunks_for_failed = sum(len(chunks_by_doc.get(did, [])) for did in failed_doc_ids)
chunks_for_processing = sum(len(chunks_by_doc.get(did, [])) for did in processing_doc_ids)

print(f"\n=== Pre-parsed Text Chunks in kv_store_text_chunks ===")
print(f"Total pre-parsed chunks: {len(text_chunks)}")
print(f"Chunks belonging to 26 PROCESSED docs: {chunks_for_processed}")
print(f"Chunks belonging to 82 FAILED docs: {chunks_for_failed}")
print(f"Chunks belonging to 1 PROCESSING doc: {chunks_for_processing}")
print(f"Failed docs with 0 pre-parsed chunks: {sum(1 for did in failed_doc_ids if did not in chunks_by_doc)}")
