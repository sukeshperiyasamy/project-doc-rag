import time
import json
from pathlib import Path
import psutil
import ollama

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

with open(Path(r"C:\Research-Knowledge-Base\rag_storage\selected_10_benchmark_candidates.json"), "r", encoding="utf-8") as f:
    candidates = json.load(f)

test_chunk = candidates[0]["content"][:2000]

print(f"Cores logical: {psutil.cpu_count(logical=True)}, physical: {psutil.cpu_count(logical=False)}")

for num_predict in [384, 512]:
    t0 = time.time()
    res = ollama.chat(
        model="qwen2.5:3b",
        messages=[
            {"role": "system", "content": CONCISE_SYSTEM_PROMPT},
            {"role": "user", "content": f"Extract entities and relationships from the following research text:\n\n{test_chunk}"}
        ],
        format="json",
        options={
            "temperature": 0.0,
            "num_predict": num_predict,
            "num_ctx": 2048,
            "num_thread": 8
        }
    )
    dt = time.time() - t0
    txt = res["message"]["content"]
    try:
        d = json.loads(txt)
        ent_cnt = len(d.get("entities", []))
        rel_cnt = len(d.get("relationships", []))
        print(f"num_predict={num_predict} -> time={dt:.2f}s | chars={len(txt)} | entities={ent_cnt} | relations={rel_cnt}")
    except Exception as e:
        print(f"num_predict={num_predict} -> error: {e}")
