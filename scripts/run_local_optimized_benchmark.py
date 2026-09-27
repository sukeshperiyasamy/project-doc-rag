import os
import sys
import json
import time
import re
import psutil
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

WORKING_DIR = Path(r"C:\Research-Knowledge-Base\rag_storage")
OUTPUT_FILE = WORKING_DIR / "local_optimized_benchmark_results.json"
INPUT_FILE = WORKING_DIR / "curated_22_optimized_benchmark_chunks.json"

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
- Other: Contextual research entities not covered above

Instructions:
1. Extract ALL named scientific entities matching these types. Preserve exact technical values, numbers, and units (e.g. "0.1 mg/mL", "784.9 nm", "930 cm-1", "2 min etch").
2. Extract binary relationships between extracted entities. Ensure source and target entities match extracted entity names.
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

def validate_extraction_json(raw_text: str):
    """Thoroughly validate JSON structure, entity schemas, and relationship references."""
    # Strip potential markdown formatting if model accidentally wrapped in fences
    cleaned = raw_text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except Exception as e:
        return False, f"JSON parse error: {e}", [], []

    if not isinstance(data, dict):
        return False, "Root is not a JSON object", [], []

    if "entities" not in data or "relationships" not in data:
        return False, "Missing 'entities' or 'relationships' key", [], []

    raw_entities = data["entities"]
    raw_relationships = data["relationships"]

    if not isinstance(raw_entities, list) or not isinstance(raw_relationships, list):
        return False, "'entities' or 'relationships' is not a list", [], []

    valid_entities = []
    entity_names = set()
    for idx, e in enumerate(raw_entities):
        if not isinstance(e, dict):
            continue
        name = str(e.get("name", "")).strip()
        etype = str(e.get("type", "")).strip()
        desc = str(e.get("description", "")).strip()
        if name and etype:
            valid_entities.append({"name": name, "type": etype, "description": desc})
            entity_names.add(name.lower())

    valid_relationships = []
    for idx, r in enumerate(raw_relationships):
        if not isinstance(r, dict):
            continue
        src = str(r.get("source", "")).strip()
        tgt = str(r.get("target", "")).strip()
        desc = str(r.get("description", "")).strip()
        keywords = str(r.get("keywords", "")).strip()
        try:
            weight = float(r.get("weight", 1.0))
        except (ValueError, TypeError):
            weight = 1.0

        if src and tgt:
            valid_relationships.append({
                "source": src,
                "target": tgt,
                "description": desc,
                "keywords": keywords,
                "weight": weight
            })

    # Empty validation check: if source text had real content, empty extraction is rejected
    if len(valid_entities) == 0:
        return False, "Extraction returned 0 valid entities", valid_entities, valid_relationships

    return True, None, valid_entities, valid_relationships

def run_benchmark():
    print("=" * 85)
    print("STARTING OPTIMIZED LOCAL BENCHMARK (Ollama qwen2.5:3b) - 22 CHUNKS")
    print("=" * 85)

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    # Resume from existing results if present
    results = []
    processed_indices = set()
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                prev_data = json.load(f)
                prev_results = prev_data.get("results", [])
                for r in prev_results:
                    if r.get("success"):
                        results.append(r)
                        processed_indices.add(r["chunk_number"])
            print(f"Resuming benchmark: {len(processed_indices)} chunks already completed.")
        except Exception as e:
            print(f"Note: Could not parse previous results file ({e}), starting fresh.")
            results = []
            processed_indices = set()

    total_chunks = len(chunks)
    benchmark_start = time.time()

    # Pre-warm psutil CPU
    psutil.cpu_percent(interval=None)

    for c in chunks:
        idx = c["index"]
        filename = c["filename"]
        category = c["category"]
        text = c["content"]
        char_len = len(text)
        est_tokens = len(text.split()) * 1.35  # Approximate token multiplier

        if idx in processed_indices:
            print(f"[{idx:02d}/{total_chunks:02d}] {filename} -- ALREADY COMPLETED (Skipping)")
            continue

        print(f"\n[{idx:02d}/{total_chunks:02d}] {filename}")
        print(f"     Category: {category}")
        print(f"     Input: {char_len} chars (~{int(est_tokens)} tokens)")

        proc = psutil.Process()
        ram_before = proc.memory_info().rss / (1024 * 1024)
        sys_ram_before = psutil.virtual_memory().percent
        psutil.cpu_percent(interval=None)

        attempt = 1
        max_attempts = 2
        success = False
        final_entities = []
        final_relationships = []
        validation_error = None
        current_input = text
        start_time = time.time()
        retried = False

        while attempt <= max_attempts and not success:
            try:
                # Use strict num_predict and repeat_penalty to prevent infinite loops on small 3B models
                num_pred = 1024 if attempt == 1 else 768
                rep_pen = 1.1 if attempt == 1 else 1.15

                res = ollama.chat(
                    model="qwen2.5:3b",
                    messages=[
                        {"role": "system", "content": CONCISE_SYSTEM_PROMPT},
                        {"role": "user", "content": f"Extract entities and relationships from the following research text:\n\n{current_input}"}
                    ],
                    format="json",
                    options={
                        "temperature": 0.0,
                        "num_ctx": 4096,
                        "num_predict": num_pred,
                        "repeat_penalty": rep_pen,
                        "num_thread": 8
                    }
                )
                raw_output = res["message"]["content"]
                is_valid, err_msg, entities, relationships = validate_extraction_json(raw_output)

                if is_valid:
                    success = True
                    final_entities = entities
                    final_relationships = relationships
                    validation_error = None
                else:
                    validation_error = err_msg
                    print(f"     [ATTEMPT {attempt} FAILED]: {err_msg}")
                    if attempt < max_attempts:
                        retried = True
                        print(f"     [RETRYING] Retrying with tightened text slice...")
                        # On retry, slice input to 1,600 chars focusing on core sentences
                        current_input = text[:1600]
            except Exception as call_err:
                validation_error = str(call_err)
                print(f"     [OLLAMA ERROR]: {call_err}")
                if attempt < max_attempts:
                    retried = True
                    current_input = text[:1600]
            attempt += 1

        elapsed = time.time() - start_time
        cpu_used = psutil.cpu_percent(interval=None)
        ram_after = proc.memory_info().rss / (1024 * 1024)
        sys_ram_after = psutil.virtual_memory().percent

        # Domain checks
        all_text_extracted = " ".join([e["name"] + " " + e["type"] + " " + e["description"] for e in final_entities] +
                                      [r["source"] + " " + r["target"] + " " + r["description"] for r in final_relationships]).lower()

        technical_checks = {
            "NAM_detected": bool(re.search(r"\bnam\b|nicotinamide", all_text_extracted)),
            "LPS_detected": bool(re.search(r"\blps\b|lipopolysaccharide", all_text_extracted)),
            "LTA_detected": bool(re.search(r"\blta\b|lipoteichoic", all_text_extracted)),
            "R6G_detected": bool(re.search(r"\br6g\b|rhodamine", all_text_extracted)),
            "concentrations_captured": bool(re.search(r"\b(mg/ml|ug/ml|ng/ml|um|mm|nm|pm|mol/l|concentration)\b", all_text_extracted)),
            "raman_peaks_captured": bool(re.search(r"\b(cm-1|cm⁻¹|peak|band|wavenumber|785 nm|784\.9 nm|532 nm)\b", all_text_extracted)),
            "measurements_captured": bool(re.search(r"\b(intensity|snr|enhancement factor|counts|measurement|detected|lod|limit of detection)\b", all_text_extracted)),
            "planned_experiments_captured": bool(re.search(r"\b(plan|future work|experiment|sop|protocol|doe|phase|run)\b", all_text_extracted)),
            "literature_captured": bool(re.search(r"\b(et al|literature|reference|study|published|author|paper|dossier)\b", all_text_extracted)),
            "conflicting_values_captured": bool(re.search(r"\b(conflict|unverified|discrepancy|inconsistent|uncertain|questionable|doubt|simulation vs experiment|unconfirmed)\b", all_text_extracted))
        }

        record = {
            "chunk_number": idx,
            "filename": filename,
            "category": category,
            "chunk_id": c["chunk_id"],
            "input_chars": char_len,
            "estimated_tokens": int(est_tokens),
            "extraction_time_s": round(elapsed, 2),
            "success": success,
            "json_valid": success and (validation_error is None),
            "entities_count": len(final_entities),
            "relationships_count": len(final_relationships),
            "retried": retried,
            "cpu_percent": round(cpu_used, 1),
            "proc_ram_mb": round(ram_after, 1),
            "sys_ram_percent": round(sys_ram_after, 1),
            "validation_error": validation_error,
            "technical_checks": technical_checks,
            "sample_entities": final_entities[:5],
            "sample_relationships": final_relationships[:4]
        }

        results.append(record)

        print(f"     --> Time: {elapsed:.2f}s | Success: {success} | Entities: {len(final_entities)} | Relations: {len(final_relationships)}")
        print(f"     --> CPU: {cpu_used}% | RAM: {sys_ram_after}% | Retried: {retried}")
        if not success:
            print(f"     --> Error: {validation_error}")

        # Update JSON on disk after every chunk
        interim = {
            "status": "IN_PROGRESS" if len(results) < total_chunks else "COMPLETED",
            "completed_chunks": len(results),
            "total_chunks": total_chunks,
            "results": results
        }
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(interim, f, indent=2)

    total_time = time.time() - benchmark_start
    times = [r["extraction_time_s"] for r in results]
    avg_time = sum(times) / len(times) if times else 0
    median_time = sorted(times)[len(times)//2] if times else 0
    min_time = min(times) if times else 0
    max_time = max(times) if times else 0
    success_count = sum(1 for r in results if r["success"])
    empty_count = sum(1 for r in results if r["entities_count"] == 0)
    retry_count = sum(1 for r in results if r["retried"])

    # Projection for remaining 301 chunks
    total_remaining_chunks = 301
    best_case_time_s = total_remaining_chunks * min_time
    avg_case_time_s = total_remaining_chunks * avg_time
    worst_case_time_s = total_remaining_chunks * max_time

    summary = {
        "benchmark_completed": True,
        "total_chunks": len(results),
        "successful_chunks": success_count,
        "success_rate_percent": round((success_count / len(results)) * 100, 1),
        "empty_extraction_count": empty_count,
        "empty_extraction_rate_percent": round((empty_count / len(results)) * 100, 1),
        "retried_chunks_count": retry_count,
        "retry_rate_percent": round((retry_count / len(results)) * 100, 1),
        "total_wall_time_s": round(total_time, 2),
        "avg_extraction_time_s": round(avg_time, 2),
        "median_extraction_time_s": round(median_time, 2),
        "min_extraction_time_s": round(min_time, 2),
        "max_extraction_time_s": round(max_time, 2),
        "projections_for_301_chunks": {
            "best_case_hours": round(best_case_time_s / 3600, 2),
            "average_case_hours": round(avg_case_time_s / 3600, 2),
            "worst_case_hours": round(worst_case_time_s / 3600, 2)
        },
        "results": results
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("\n" + "=" * 85)
    print("OPTIMIZED BENCHMARK COMPLETE!")
    print(f"Success Rate: {summary['success_rate_percent']}% ({success_count}/{len(results)})")
    print(f"Empty Extraction Rate: {summary['empty_extraction_rate_percent']}%")
    print(f"Average Time Per Chunk: {avg_time:.2f}s (Median: {median_time:.2f}s, Min: {min_time:.2f}s, Max: {max_time:.2f}s)")
    print(f"Projected Total Ingestion Time for 301 Chunks:")
    print(f"   * Best Case:    {summary['projections_for_301_chunks']['best_case_hours']} hours")
    print(f"   * Average Case: {summary['projections_for_301_chunks']['average_case_hours']} hours")
    print(f"   * Worst Case:   {summary['projections_for_301_chunks']['worst_case_hours']} hours")
    print("=" * 85)

if __name__ == "__main__":
    run_benchmark()
