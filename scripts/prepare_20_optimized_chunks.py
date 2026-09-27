import json
import re
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

target_matrix = [
    ("Experiment_Report_R6G_NAM_2m5m10m_12Aug2026.docx", "R6G & NAM SERS Measurements", ["R6G", "NAM", "784.9 nm", "SNR"]),
    ("Experiment_Plan_LPS.docx", "LPS Planned Experiments & Peak Targets", ["LPS", "peak targets", "concentration"]),
    ("LTA_Raman_Characterization_Report.docx", "LTA Raman Characterization & Spectral Peaks", ["LTA", "cm-1", "matched-blank"]),
    ("LTA_Evidence_Assessment.docx", "LTA Simulation vs Powder Raman vs SERS", ["LTA", "simulation vs experiment", "DFT"]),
    ("Preparation of NAM Stock solution.docx", "NAM Stock Preparation & Concentrations", ["stock solution", "mg/mL", "NAM"]),
    ("NAM_SERS_Literature_Review_101_Papers_Aug2026.docx", "Literature Review & Substrate Fabrication", ["literature", "papers", "SERS"]),
    ("simulation vs experiment.docx", "Conflicting/Unverified Values: DFT vs Exp", ["MurNAc", "discrepancy", "simulation"]),
    ("SOP_MACE_NAM_SERS_Bench_Protocol_Aug2026.docx", "SOP Protocol: MACE & Cleaning", ["SOP", "MACE", "functionalization"]),
    ("NAM_Detection_Technology_Comparison_and_Strategy_Aug2026.docx", "NAM Cross-Technology Comparison & LOD", ["Limit of Detection", "Plan A", "biosensor"]),
    ("sepsis_biomarker_state_of_art.docx", "Multi-Marker State of the Art: NAM, LPS, LTA", ["NAM", "LPS", "LTA", "Limit of Detection"]),
    ("Boronic_Acid_Design_Rationale.docx", "Boronic Acid Capture Chemistry", ["boronic acid", "capture", "NAM"]),
    ("Next_Experiment_Plan_BareAg_NAM_Optimization_12Aug2026.docx", "Planned Experiments: BareAg NAM Optimization", ["experiment plan", "laser power", "acquisition"]),
    ("Measurement_Worksheet_R6G_NAM_Aug12.docx", "Experimental Worksheet & Raw Measurements", ["worksheet", "measurement", "counts"]),
    ("Todays_Run_Sheet_BareAg_MACE_NAM_Aug2026.docx", "Run Sheet: BareAg MACE Protocol", ["run sheet", "laser", "integration time"]),
    ("Porous_Si_Discussion_Plan.docx", "Porous Silicon Substrate Discussion", ["porous silicon", "substrate", "fabrication"]),
    ("Power_At_Sample_Protocol.docx", "Instrument Parameters: Power at Sample", ["power at sample", "laser power", "mW"]),
    ("R6G_Research_Briefing.docx", "R6G SERS Enhancement Briefing", ["R6G", "enhancement factor", "spectral"]),
    ("Project_Status_Report_Sepsis_SERS_As_of_August_2026.docx", "Project Status: Sepsis Biomarker SERS", ["sepsis", "biomarker", "SERS status"]),
    ("NAM_Capture_Strategies.docx", "NAM Capture Strategies Comparison", ["capture strategy", "functionalization", "NAM"]),
    ("Updated_Project_Progress_Report_With_Experiments.docx", "Updated Project Report with Experiments", ["progress", "experiment", "findings"]),
    ("Sukesh_M24IM1007_Report_Converted.docx", "Comprehensive Project Report & Patent Landscape", ["patent", "landscape", "M24IM1007"]),
    ("Sepsis_SERS_Slide_Content_Draft.docx", "Sepsis SERS Slide Content: Rationale & Methods", ["rationale", "SERS", "diagnostics"])
]

selected = []

for filename, category, key_terms in target_matrix:
    matched_doc_ids = [did for did, d in failed_docs.items() if d["name"] == filename]
    if not matched_doc_ids:
        continue
    did = matched_doc_ids[0]
    doc_chunks = [(cid, cdata) for cid, cdata in chunks.items() if cdata.get("full_doc_id") == did]
    if not doc_chunks:
        continue
    
    chosen_cid, chosen_data = doc_chunks[0]
    full_text = chosen_data.get("content", "")
    
    for cid, cdata in doc_chunks:
        txt = cdata.get("content", "")
        if any(term.lower() in txt.lower() for term in key_terms):
            chosen_cid = cid
            chosen_data = cdata
            full_text = txt
            break
            
    if len(full_text) > 2400:
        cutoff = full_text.find("\n\n", 1800)
        if cutoff != -1 and cutoff <= 2500:
            optimized_text = full_text[:cutoff].strip()
        else:
            cutoff_single = full_text.find("\n", 2000)
            if cutoff_single != -1 and cutoff_single <= 2500:
                optimized_text = full_text[:cutoff_single].strip()
            else:
                optimized_text = full_text[:2300].strip()
    else:
        optimized_text = full_text.strip()
        
    selected.append({
        "index": len(selected) + 1,
        "filename": filename,
        "doc_id": did,
        "chunk_id": chosen_cid,
        "category": category,
        "key_terms": key_terms,
        "char_length": len(optimized_text),
        "word_length": len(optimized_text.split()),
        "content": optimized_text
    })

print(f"Prepared {len(selected)} curated representative chunks:")
for item in selected:
    print(f"[{item['index']:02d}] {item['filename']} ({item['category']}) - {item['char_length']} chars, {item['word_length']} words")

with open(WORKING_DIR / "curated_22_optimized_benchmark_chunks.json", "w", encoding="utf-8") as f:
    json.dump(selected, f, indent=2)
