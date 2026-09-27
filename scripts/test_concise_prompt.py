import os
import sys
import json
import time
import psutil
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

# Concise scientific system prompt with custom entity types
CONCISE_SYSTEM_PROMPT = """You are a scientific Knowledge Graph specialist extracting entities and relationships from medical, biochemical, and spectroscopic research text.

Entity Types:
- Biomarker: Biological molecules, markers (e.g. NAM, LPS, LTA, bilirubin)
- Chemical: Reagents, solvents, salts, ligands (e.g. boronic acid, ethanol, PBS)
- Material: Nanoparticles, colloidal solutions, metals (e.g. silver nanoparticles, gold nanostars)
- Substrate: Solid substrates, fabrication platforms (e.g. Black Silicon, etched silicon)
- Instrument: Hardware, spectrometers (e.g. Raman spectrometer, SEM)
- Instrument_Parameter: Operating parameters (e.g. 785 nm, 532 nm, 10s integration, 10 mW)
- Spectral_Peak: Raman peaks, bands, wavenumbers (e.g. 930 cm-1, 1580 cm-1, D band, G band)
- Concentration: Numerical concentrations (e.g. 0.1 mg/mL, 1 uM, 10 mM)
- Measurement: Readings, intensities, SNR, enhancement factors, LOD
- Result: Detection outcomes, status (e.g. Detected, Not Detected)
- Method_Protocol: Protocols, fabrication SOPs, SERS measurement SOPs
- Author_Paper: Cited papers, researchers, literature references
- Problem_Cause: Failure modes, spectral interference, fouling, degradation

Instructions:
1. Extract ALL named scientific entities matching these types. Preserve exact technical values, numbers, and units (e.g. "0.1 mg/mL", "784.9 nm", "930 cm-1", "2 min etch").
2. Extract binary relationships between extracted entities.
3. Return ONLY a valid JSON object matching this exact schema:
{
  "entities": [
    {"name": "Exact Name", "type": "EntityType", "description": "Concise factual description"}
  ],
  "relationships": [
    {"source": "Entity1", "target": "Entity2", "description": "Relationship description", "keywords": "keyword1, keyword2", "weight": 1.0}
  ]
}
Do NOT include markdown fences, preambles, or commentary outside the JSON."""

import ollama

# Let's test with a representative 2,000 character snippet from Experiment_Report_R6G_NAM_2m5m10m_12Aug2026.docx
with open(Path(r"C:\Research-Knowledge-Base\rag_storage\selected_10_benchmark_candidates.json"), "r", encoding="utf-8") as f:
    candidates = json.load(f)

test_chunk = candidates[0]["content"][:2200]
print(f"Testing input size: {len(test_chunk)} characters (~{len(test_chunk.split())} words)")
print(f"Preview:\n{test_chunk[:300]}...\n")

t0 = time.time()
res = ollama.chat(
    model="qwen2.5:3b",
    messages=[
        {"role": "system", "content": CONCISE_SYSTEM_PROMPT},
        {"role": "user", "content": f"Extract entities and relationships from the following research text:\n\n{test_chunk}"}
    ],
    format="json",
    options={"temperature": 0.0}
)
elapsed = time.time() - t0
output_text = res["message"]["content"]

print(f"Extraction completed in: {elapsed:.2f} seconds!")
print(f"Output character count: {len(output_text)}")
try:
    parsed = json.loads(output_text)
    entities = parsed.get("entities", [])
    relations = parsed.get("relationships", [])
    print(f"Entities extracted: {len(entities)}")
    print(f"Relationships extracted: {len(relations)}")
    print("\nSample Entities:")
    for e in entities[:8]:
        print(f"  * [{e.get('type')}] {e.get('name')}: {e.get('description')}")
    print("\nSample Relationships:")
    for r in relations[:5]:
        print(f"  * {r.get('source')} -> {r.get('target')} ({r.get('keywords')}): {r.get('description')}")
except Exception as e:
    print("JSON Parse error:", e)
    print("Raw output:", output_text[:500])
