import json
import re
import sys
from pathlib import Path

WORKING_DIR = Path(r"C:\Research-Knowledge-Base\rag_storage")
CHUNKS_PATH = WORKING_DIR / "kv_store_text_chunks.json"
DOC_CAT_PATH = WORKING_DIR / "doc_status_categorized.json"

with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
    chunks = json.load(f)

with open(DOC_CAT_PATH, "r", encoding="utf-8") as f:
    doc_cat = json.load(f)

failed_docs = {d["doc_id"]: d for d in doc_cat["failed"]}

# Let's inspect documents with different focuses:
# 1. NAM detection & SERS substrate engineering
# 2. LPS detection & experimental plan
# 3. LTA complete evidence & characterization report
# 4. Experimental measurements & Raman spectra / peaks (e.g. 785nm, 930 cm-1, etc.)
# 5. Planned experiments / DOE / SOP
# 6. Literature / external studies (101 papers review, state of the art)
# 7. Concentrations / dilution curves (e.g., ug/mL, mg/mL, nM)
# 8. Derived / calculated values (enhancement factor, S/N, ratios)
# 9. Conflicting / unverified values / discrepancies
# 10. Multi-marker or clinical translation / patent / status report

# Let's inspect chunks per document
docs_with_chunks = {}
for cid, cdata in chunks.items():
    did = cdata.get("full_doc_id")
    if did in failed_docs:
        docs_with_chunks.setdefault(failed_docs[did]["name"], []).append((cid, cdata))

print(f"Total failed docs with chunks: {len(docs_with_chunks)}")
for name, ch_list in sorted(docs_with_chunks.items()):
    print(f"  {name}: {len(ch_list)} chunks")
