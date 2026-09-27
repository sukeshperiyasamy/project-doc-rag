"""
Calculate complete ingestion inventory for all documents in C:\\Users\\sukes\\Downloads\\mtp
Maps exactly to processed, duplicate, target, empty, and chunk counts.
"""

import sys
import json
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

from file_text_extractor import (
    SOURCE_DIR,
    RAG_DIR,
    EXCLUDED_EXT,
    SUPPORTED_EXT,
    DUPLICATE_FILES,
    extract_text,
    chunk_text
)

# Load already processed documents
with open(RAG_DIR / "doc_status_categorized.json", "r", encoding="utf-8") as f:
    cat = json.load(f)

processed_names = {Path(d["name"]).name for d in cat["processed"]}

all_source_files = sorted(list(SOURCE_DIR.iterdir()), key=lambda x: x.name)

categories = {
    "already_processed": [],
    "excluded_excel": [],
    "unsupported_ext": [],
    "duplicate_skipped": [],
    "target_for_ingestion": []
}

for sf in all_source_files:
    if not sf.is_file():
        continue
    name = sf.name
    ext = sf.suffix.lower()

    if ext in EXCLUDED_EXT:
        categories["excluded_excel"].append(name)
        continue
    if ext not in SUPPORTED_EXT:
        categories["unsupported_ext"].append(name)
        continue
    if name in processed_names:
        categories["already_processed"].append(name)
        continue
    if name in DUPLICATE_FILES:
        categories["duplicate_skipped"].append(name)
        continue

    categories["target_for_ingestion"].append(name)

print("=" * 80)
print("SOURCE REPOSITORY INVENTORY AUDIT")
print("=" * 80)
print(f"Total files in source directory: {len(all_source_files)}")
print(f"1. Already Processed (PROTECTED):  {len(categories['already_processed'])}")
print(f"2. Excluded Excel (.xlsx/.xls):    {len(categories['excluded_excel'])}")
print(f"3. Duplicate Skipped (Identical):  {len(categories['duplicate_skipped'])}")
print(f"4. Unsupported Extensions:         {len(categories['unsupported_ext'])}")
print(f"5. Target for Local Ingestion:     {len(categories['target_for_ingestion'])}")
print("=" * 80)

print("\nExtracting and chunking target files...")
chunk_inventory = []
empty_files = []
total_chunks = 0

for idx, name in enumerate(categories["target_for_ingestion"]):
    fp = SOURCE_DIR / name
    txt = extract_text(fp)
    chunks = chunk_text(txt, target_size=2000, overlap=220)
    chunk_count = len(chunks)
    total_chunks += chunk_count

    record = {
        "index": idx + 1,
        "name": name,
        "extension": fp.suffix.lower(),
        "char_length": len(txt),
        "chunk_count": chunk_count,
        "chunks": chunks
    }
    chunk_inventory.append(record)

    if chunk_count == 0:
        empty_files.append(name)
        print(f"[{idx+1:02d}/{len(categories['target_for_ingestion']):02d}] {name} -> 0 chunks (EMPTY / OCR NEEDED)")
    else:
        print(f"[{idx+1:02d}/{len(categories['target_for_ingestion']):02d}] {name} -> {chunk_count} chunks ({len(txt)} chars)")

print("\n" + "=" * 80)
print("TARGET INGESTION METRICS")
print("=" * 80)
print(f"Target files: {len(categories['target_for_ingestion'])}")
print(f"Files with text: {len(categories['target_for_ingestion']) - len(empty_files)}")
print(f"Files with 0 text (empty/scanned): {len(empty_files)}")
print(f"Total chunks to extract: {total_chunks}")
print("=" * 80)

# Save target manifest for ingestion pipeline
summary_manifest = {
    "total_source_files": len(all_source_files),
    "already_processed_count": len(categories["already_processed"]),
    "excluded_excel_count": len(categories["excluded_excel"]),
    "duplicate_skipped_count": len(categories["duplicate_skipped"]),
    "target_files_count": len(categories["target_for_ingestion"]),
    "files_with_chunks_count": len(categories["target_for_ingestion"]) - len(empty_files),
    "empty_files_count": len(empty_files),
    "empty_files": empty_files,
    "total_chunks_to_process": total_chunks,
    "already_processed": categories["already_processed"],
    "excluded_excel": categories["excluded_excel"],
    "duplicate_skipped": categories["duplicate_skipped"],
    "targets": [
        {
            "index": c["index"],
            "name": c["name"],
            "extension": c["extension"],
            "char_length": c["char_length"],
            "chunk_count": c["chunk_count"]
        }
        for c in chunk_inventory
    ]
}

with open(RAG_DIR / "target_ingestion_manifest.json", "w", encoding="utf-8") as f:
    json.dump(summary_manifest, f, indent=2)

print(f"\nSaved target manifest to {RAG_DIR / 'target_ingestion_manifest.json'}")
