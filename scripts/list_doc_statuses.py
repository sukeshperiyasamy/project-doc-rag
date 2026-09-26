import json
from pathlib import Path

WORKING_DIR = Path(r"C:\Research-Knowledge-Base\rag_storage")
DOC_STATUS_PATH = WORKING_DIR / "kv_store_doc_status.json"

with open(DOC_STATUS_PATH, "r", encoding="utf-8") as f:
    doc_status = json.load(f)

processed_docs = []
failed_docs = []
processing_docs = []
other_docs = []

for doc_id, data in doc_status.items():
    st = data.get("status")
    name = data.get("file_path") or data.get("metadata", {}).get("source_file") or data.get("content_summary")[:40]
    chunks_count = data.get("chunks_count", 0)
    err = data.get("error") or data.get("metadata", {}).get("error")
    
    info = {
        "doc_id": doc_id,
        "name": name,
        "chunks_count": chunks_count,
        "status": st,
        "error": err,
        "created_at": data.get("created_at"),
        "updated_at": data.get("updated_at")
    }
    
    if st == "processed":
        processed_docs.append(info)
    elif st == "failed":
        failed_docs.append(info)
    elif st == "processing":
        processing_docs.append(info)
    else:
        other_docs.append(info)

print(f"PROCESSED ({len(processed_docs)}):")
for d in sorted(processed_docs, key=lambda x: str(x['name'])):
    print(f"  - {d['name']} (chunks: {d['chunks_count']}, id: {d['doc_id']})")

print(f"\nPROCESSING ({len(processing_docs)}):")
for d in processing_docs:
    print(f"  - {d['name']} (chunks: {d['chunks_count']}, id: {d['doc_id']})")

print(f"\nFAILED ({len(failed_docs)}):")
for d in sorted(failed_docs, key=lambda x: str(x['name'])):
    err_preview = str(d['error'])[:80] if d['error'] else "No explicit error recorded in status"
    print(f"  - {d['name']} (chunks: {d['chunks_count']}) | {err_preview}")

# Write to a JSON file for safe reference
report = {
    "processed_count": len(processed_docs),
    "failed_count": len(failed_docs),
    "processing_count": len(processing_docs),
    "processed": processed_docs,
    "processing": processing_docs,
    "failed": failed_docs
}

with open(WORKING_DIR / "doc_status_categorized.json", "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)

print("\nWrote categorized report to rag_storage/doc_status_categorized.json")
