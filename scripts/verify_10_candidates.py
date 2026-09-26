import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

WORKING_DIR = Path(r"C:\Research-Knowledge-Base\rag_storage")
CHUNKS_PATH = WORKING_DIR / "kv_store_text_chunks.json"
DOC_CAT_PATH = WORKING_DIR / "doc_status_categorized.json"

with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
    chunks = json.load(f)

with open(DOC_CAT_PATH, "r", encoding="utf-8") as f:
    doc_cat = json.load(f)

failed_docs = {d["doc_id"]: d for d in doc_cat["failed"]}

target_files = [
    ("Experiment_Report_R6G_NAM_2m5m10m_12Aug2026.docx", "NAM & R6G Experimental Measurements & Raman Peaks"),
    ("Experiment_Plan_LPS.docx", "LPS Planned Experiments & Concentrations"),
    ("LTA_Raman_Characterization_Report.docx", "LTA Raman Characterization & Spectral Peaks"),
    ("LTA_Evidence_Assessment.docx", "LTA Evidence Assessment & Simulation vs Experiment"),
    ("Preparation of NAM Stock solution.docx", "NAM Concentrations & Derived/Calculated Values"),
    ("NAM_SERS_Literature_Review_101_Papers_Aug2026.docx", "Literature/External Studies (101 Papers)"),
    ("simulation vs experiment.docx", "Conflicting/Unverified Values: Simulation vs Experiment"),
    ("SOP_MACE_NAM_SERS_Bench_Protocol_Aug2026.docx", "Planned Experiments & SOP Protocol"),
    ("NAM_Detection_Technology_Comparison_and_Strategy_Aug2026.docx", "Concentrations, Measurements & LOD"),
    ("sepsis_biomarker_state_of_art.docx", "Multi-marker State of the Art (NAM, LPS, LTA)")
]

selected_candidates = []

for filename, category in target_files:
    # Find matching doc_id
    matching_docs = [did for did, d in failed_docs.items() if d["name"] == filename]
    if not matching_docs:
        print(f"[MISSING] {filename}")
        continue
    did = matching_docs[0]
    # find chunks
    doc_chunks = [(cid, cdata) for cid, cdata in chunks.items() if cdata.get("full_doc_id") == did]
    print(f"\n========================================================")
    print(f"File: {filename} ({category}) - {len(doc_chunks)} chunks available")
    for i, (cid, cdata) in enumerate(doc_chunks):
        content = cdata.get("content", "")
        tokens = cdata.get("tokens", len(content.split()))
        print(f"  Chunk [{i}] ID: {cid} | Length: {len(content)} chars (~{tokens} tokens)")
        print(f"  Snippet: {content[:150].strip()}...")
    if doc_chunks:
        # Pick the chunk with richest content (e.g. index 0 or largest)
        best_chunk = max(doc_chunks, key=lambda x: len(x[1].get("content", "")))
        selected_candidates.append({
            "category": category,
            "filename": filename,
            "chunk_id": best_chunk[0],
            "doc_id": did,
            "content": best_chunk[1].get("content", "")
        })

print(f"\nSelected {len(selected_candidates)} candidates.")
with open(WORKING_DIR / "selected_10_benchmark_candidates.json", "w", encoding="utf-8") as f:
    json.dump(selected_candidates, f, indent=2)
