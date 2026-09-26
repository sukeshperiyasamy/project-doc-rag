import os
import json
from pathlib import Path

SOURCE_DIR = Path(r"C:\Users\sukes\Downloads\mtp")
INPUT_DIR = Path(r"C:\Research-Knowledge-Base\inputs")
WORKING_DIR = Path(r"C:\Research-Knowledge-Base\rag_storage")
DOC_STATUS_PATH = WORKING_DIR / "kv_store_doc_status.json"
MANIFEST_PATH = WORKING_DIR / "sync_manifest.json"

EXCLUDED_EXT = {".xlsx", ".xls"}
SUPPORTED_EXT = {".docx", ".pdf", ".csv", ".txt", ".md", ".pptx"}

def analyze():
    # 1. Source files
    source_files = {}
    if SOURCE_DIR.exists():
        for p in SOURCE_DIR.iterdir():
            if p.is_file():
                ext = p.suffix.lower()
                source_files[p.name] = {
                    "ext": ext,
                    "supported": (ext in SUPPORTED_EXT and ext not in EXCLUDED_EXT),
                    "size": p.stat().st_size
                }
    
    # 2. Input files
    input_files = {}
    if INPUT_DIR.exists():
        for p in INPUT_DIR.iterdir():
            if p.is_file():
                input_files[p.name] = {
                    "ext": p.suffix.lower(),
                    "size": p.stat().st_size
                }

    # 3. doc status
    doc_status = {}
    if DOC_STATUS_PATH.exists():
        with open(DOC_STATUS_PATH, "r", encoding="utf-8") as f:
            doc_status = json.load(f)

    # 4. sync manifest
    manifest = {}
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            manifest = json.load(f)

    print(f"Total files in source: {len(source_files)}")
    source_supported = [name for name, d in source_files.items() if d["supported"]]
    print(f"Supported files in source: {len(source_supported)}")
    print(f"Total files in inputs/: {len(input_files)}")
    print(f"Total records in kv_store_doc_status.json: {len(doc_status)}")
    print(f"Total records in sync_manifest.json: {len(manifest)}")

    status_counts = {}
    for doc_id, data in doc_status.items():
        st = data.get("status")
        status_counts[st] = status_counts.get(st, 0) + 1
    print("\nDoc status breakdown in kv_store_doc_status.json:")
    for st, count in status_counts.items():
        print(f"  {st}: {count}")

    # Check differences
    doc_status_keys = set(doc_status.keys())
    # Note: doc_status keys might be doc_id or file_path or content_summary or filename. Let's see how keys look:
    sample_keys = list(doc_status.keys())[:5]
    print(f"\nSample doc_status keys: {sample_keys}")
    
    # Check if doc_status keys match input_files or source_files
    # Let's see what keys are stored
    file_names_in_status = set()
    for k, v in doc_status.items():
        fn = v.get("file_path") or v.get("content_summary") or k
        file_names_in_status.add(Path(str(fn)).name)

    source_supported_set = set(source_supported)
    inputs_set = set(input_files.keys())

    missing_in_status = source_supported_set - file_names_in_status
    print(f"\nSupported source files NOT in doc_status ({len(missing_in_status)}):")
    for m in sorted(missing_in_status):
        print(f"  - {m}")

    missing_in_inputs = source_supported_set - inputs_set
    print(f"\nSupported source files NOT in inputs/ ({len(missing_in_inputs)}):")
    for m in sorted(missing_in_inputs):
        print(f"  - {m}")

    inputs_not_in_status = inputs_set - file_names_in_status
    print(f"\nInputs NOT in doc_status ({len(inputs_not_in_status)}):")
    for m in sorted(inputs_not_in_status):
        print(f"  - {m}")

if __name__ == "__main__":
    analyze()
