import json
import re
from pathlib import Path

WORKING_DIR = Path(r"C:\Research-Knowledge-Base\rag_storage")
CHUNKS_PATH = WORKING_DIR / "kv_store_text_chunks.json"
DOC_CAT_PATH = WORKING_DIR / "doc_status_categorized.json"

with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
    chunks = json.load(f)

with open(DOC_CAT_PATH, "r", encoding="utf-8") as f:
    doc_cat = json.load(f)

failed_docs = {d["doc_id"]: d for d in doc_cat["failed"]}

failed_chunks_list = []
for cid, cdata in chunks.items():
    doc_id = cdata.get("full_doc_id")
    if doc_id in failed_docs:
        failed_chunks_list.append({
            "chunk_id": cid,
            "doc_id": doc_id,
            "doc_name": failed_docs[doc_id]["name"],
            "content": cdata.get("content", ""),
            "tokens": cdata.get("tokens", len(cdata.get("content", "").split()))
        })

print(f"Total failed chunks available: {len(failed_chunks_list)}")

# Keywords to match
keywords = {
    "NAM": re.compile(r"\bNAM\b|nicotinamide", re.IGNORECASE),
    "LPS": re.compile(r"\bLPS\b|lipopolysaccharide", re.IGNORECASE),
    "LTA": re.compile(r"\bLTA\b|lipoteichoic", re.IGNORECASE),
    "concentrations": re.compile(r"\b(mg/mL|ug/mL|ng/mL|uM|mM|nM|pM|mol/L)\b", re.IGNORECASE),
    "Raman peaks": re.compile(r"\b(cm-1|cm⁻¹|peak|band|wavenumber|785\s*nm|532\s*nm)\b", re.IGNORECASE),
    "measurements": re.compile(r"\b(intensity|enhancement factor|LOD|limit of detection|SNR|counts)\b", re.IGNORECASE),
    "planned experiments": re.compile(r"\b(plan|future work|experiment|run sheet|protocol|SOP|DOE)\b", re.IGNORECASE),
    "literature/external": re.compile(r"\b(et al|literature|reported by|reference|study|published)\b", re.IGNORECASE),
    "derived/calculated": re.compile(r"\b(calculated|derived|estimated|ratio|equation|formula)\b", re.IGNORECASE),
    "conflicting/unverified": re.compile(r"\b(conflict|unverified|discrepancy|inconsistent|uncertain|questionable|doubt)\b", re.IGNORECASE)
}

scored_chunks = []
for item in failed_chunks_list:
    text = item["content"]
    matched_keys = [k for k, pattern in keywords.items() if pattern.search(text)]
    item["matched_keys"] = matched_keys
    item["score"] = len(matched_keys)
    scored_chunks.append(item)

scored_chunks.sort(key=lambda x: x["score"], reverse=True)

print("\nTop 15 candidates by diverse keyword coverage:")
for i, sc in enumerate(scored_chunks[:15]):
    print(f"\n[{i+1}] Doc: {sc['doc_name']} | Chunk: {sc['chunk_id']}")
    print(f"    Length: {len(sc['content'])} chars | Matches ({sc['score']}): {sc['matched_keys']}")
    print(f"    Preview: {sc['content'][:150]}...")

# Save all scored chunks to file for selection
with open(WORKING_DIR / "scored_failed_chunks.json", "w", encoding="utf-8") as f:
    json.dump(scored_chunks, f, indent=2)
