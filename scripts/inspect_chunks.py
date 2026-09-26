import json
from pathlib import Path

WORKING_DIR = Path(r"C:\Research-Knowledge-Base\rag_storage")
CHUNKS_PATH = WORKING_DIR / "kv_store_text_chunks.json"
DOC_STATUS_PATH = WORKING_DIR / "doc_status_categorized.json"

with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
    chunks = json.load(f)

with open(DOC_STATUS_PATH, "r", encoding="utf-8") as f:
    doc_cat = json.load(f)

print(f"Total chunks in kv_store_text_chunks.json: {len(chunks)}")

failed_docs = {d["doc_id"]: d for d in doc_cat["failed"]}
processing_docs = {d["doc_id"]: d for d in doc_cat["processing"]}

failed_chunks = {}
for chunk_id, chunk_data in chunks.items():
    doc_id = chunk_data.get("full_doc_id")
    if doc_id in failed_docs:
        failed_chunks.setdefault(doc_id, []).append((chunk_id, chunk_data))

print(f"Failed docs with chunks already in text_chunks: {len(failed_chunks)} out of {len(failed_docs)}")
total_failed_chunk_count = sum(len(c) for c in failed_chunks.values())
print(f"Total chunks belonging to failed docs: {total_failed_chunk_count}")

# Also check chunks in failed_docs from doc_status
total_chunks_in_doc_status = sum(d["chunks_count"] for d in doc_cat["failed"])
print(f"Total chunks_count listed in failed doc_status: {total_chunks_in_doc_status}")
