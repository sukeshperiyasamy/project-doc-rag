import os
import sys
import json
import time
import re
import psutil
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

WORKING_DIR = Path(r"C:\Research-Knowledge-Base\rag_storage")
CONFIG_DIR = Path(r"C:\Research-Knowledge-Base\config")
os.environ["PROMPT_DIR"] = str(CONFIG_DIR)

from lightrag.prompt import PROMPTS, resolve_entity_extraction_prompt_profile
from lightrag.operate import _process_json_extraction_result
from lightrag.utils import tolerant_load_json_dict
import ollama

def run_benchmark():
    print("=" * 80)
    print("STARTING 10-CHUNK LOCAL BENCHMARK WITH OLLAMA (qwen2.5:3b)")
    print("=" * 80)

    # 1. Resolve prompt profile
    prof = resolve_entity_extraction_prompt_profile(
        {"entity_type_prompt_file": "entity_type_prompt.yml"},
        use_json=True
    )
    entity_types_guidance = prof["entity_types_guidance"]
    examples = prof["entity_extraction_json_examples"][0] if prof["entity_extraction_json_examples"] else ""
    language = "English"
    max_total_records = 30
    max_entity_records = 20

    system_prompt = PROMPTS["entity_extraction_json_system_prompt"].format(
        entity_types_guidance=entity_types_guidance,
        examples=examples,
        language=language,
        max_total_records=max_total_records,
        max_entity_records=max_entity_records,
    )

    # 2. Load the 10 selected candidates
    with open(WORKING_DIR / "selected_10_benchmark_candidates.json", "r", encoding="utf-8") as f:
        candidates = json.load(f)

    results = []
    total_chunks = len(candidates)
    benchmark_start_time = time.time()

    # Pre-warm CPU monitor
    psutil.cpu_percent(interval=None)

    for idx, c in enumerate(candidates, 1):
        print(f"\n[{idx}/{total_chunks}] Benchmarking: {c['filename']}")
        print(f"    Category: {c['category']}")
        print(f"    Chunk ID: {c['chunk_id']}")
        chunk_content = c["content"]
        char_len = len(chunk_content)
        word_len = len(chunk_content.split())
        print(f"    Size: {char_len} chars, ~{word_len} words")

        user_prompt = PROMPTS["entity_extraction_json_user_prompt"].format(
            entity_types_guidance=entity_types_guidance,
            heading_context_block="",
            input_text=chunk_content,
            language=language,
            max_total_records=max_total_records,
            max_entity_records=max_entity_records,
        )

        proc = psutil.Process()
        ram_before_mb = proc.memory_info().rss / (1024 * 1024)
        sys_ram_before = psutil.virtual_memory().percent
        psutil.cpu_percent(interval=None)

        start_t = time.time()
        error_msg = None
        raw_output = ""
        success = False
        parsed_dict = None
        nodes_dict = {}
        edges_dict = {}

        try:
            response = ollama.chat(
                model="qwen2.5:3b",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                format="json",
                options={"temperature": 0.0}
            )
            elapsed = time.time() - start_t
            raw_output = response.get("message", {}).get("content", "")
            success = True
        except Exception as e:
            elapsed = time.time() - start_t
            error_msg = str(e)
            print(f"    [ERROR] Ollama call failed: {e}")

        cpu_used = psutil.cpu_percent(interval=None)
        ram_after_mb = proc.memory_info().rss / (1024 * 1024)
        sys_ram_after = psutil.virtual_memory().percent

        # Validation with LightRAG utilities
        json_error = None
        entities_extracted = []
        relations_extracted = []

        if success and raw_output:
            try:
                parsed_dict = tolerant_load_json_dict(raw_output)
                if not parsed_dict:
                    json_error = "tolerant_load_json_dict returned empty or unrecoverable dictionary"
                else:
                    entities_extracted = parsed_dict.get("entities", [])
                    relations_extracted = parsed_dict.get("relationships", [])
                    if not isinstance(entities_extracted, list) or not isinstance(relations_extracted, list):
                        json_error = "JSON root missing list-type 'entities' or 'relationships'"
            except Exception as pe:
                json_error = f"Parse exception: {pe}"

            # LightRAG node/edge simulation
            import asyncio
            try:
                nodes_dict, edges_dict = asyncio.run(_process_json_extraction_result(
                    result=raw_output,
                    chunk_key=c["chunk_id"],
                    timestamp=int(time.time()),
                    file_path=c["filename"],
                    parsed=parsed_dict
                ))
            except Exception as lre:
                print(f"    [WARNING] LightRAG process result error: {lre}")

        # Domain Evaluation
        entities_names = [e.get("name", "") for e in entities_extracted if isinstance(e, dict)]
        entities_types = [e.get("type", "") for e in entities_extracted if isinstance(e, dict)]
        entities_texts = " ".join([f"{e.get('name', '')} {e.get('type', '')} {e.get('description', '')}" for e in entities_extracted if isinstance(e, dict)])
        relations_texts = " ".join([f"{r.get('source', '')} {r.get('target', '')} {r.get('keywords', '')} {r.get('description', '')}" for r in relations_extracted if isinstance(r, dict)])
        all_kg_text = (entities_texts + " " + relations_texts).lower()

        domain_coverage = {
            "NAM": bool(re.search(r"\bnam\b|nicotinamide", all_kg_text)),
            "LPS": bool(re.search(r"\blps\b|lipopolysaccharide", all_kg_text)),
            "LTA": bool(re.search(r"\blta\b|lipoteichoic", all_kg_text)),
            "concentrations": bool(re.search(r"\b(mg/ml|ug/ml|ng/ml|um|mm|nm|pm|mol/l|concentration)\b", all_kg_text)),
            "Raman peaks": bool(re.search(r"\b(cm-1|cm⁻¹|peak|band|wavenumber|785 nm|784\.9 nm|532 nm)\b", all_kg_text)),
            "experimental measurements": bool(re.search(r"\b(intensity|snr|enhancement factor|counts|measurement|detected|lod|limit of detection)\b", all_kg_text)),
            "planned experiments": bool(re.search(r"\b(plan|future work|experiment|sop|protocol|doe|phase|run)\b", all_kg_text)),
            "literature/external studies": bool(re.search(r"\b(et al|literature|reference|study|published|author|paper|dossier)\b", all_kg_text)),
            "derived/calculated values": bool(re.search(r"\b(calculated|derived|ratio|estimated|equation|dilution|stock|formula)\b", all_kg_text)),
            "conflicting/unverified values": bool(re.search(r"\b(conflict|unverified|discrepancy|inconsistent|uncertain|questionable|doubt|simulation vs experiment|unconfirmed)\b", all_kg_text))
        }

        # Quality scoring
        quality_score = "Good"
        if not success or json_error or len(entities_extracted) == 0:
            quality_score = "Poor / Failed"
        elif len(entities_extracted) >= 5 and len(relations_extracted) >= 3:
            quality_score = "High"
        else:
            quality_score = "Moderate"

        chunk_record = {
            "chunk_number": idx,
            "filename": c["filename"],
            "category": c["category"],
            "chunk_id": c["chunk_id"],
            "char_length": char_len,
            "word_length": word_len,
            "extraction_time_s": round(elapsed, 2),
            "success": success and (json_error is None) and (len(entities_extracted) > 0),
            "valid_lightrag_output": len(nodes_dict) > 0,
            "nodes_count": len(nodes_dict),
            "edges_count": len(edges_dict),
            "entities_extracted_count": len(entities_extracted),
            "relations_extracted_count": len(relations_extracted),
            "cpu_percent": round(cpu_used, 1),
            "ram_proc_mb": round(ram_after_mb, 1),
            "ram_sys_percent": round(sys_ram_after, 1),
            "output_quality": quality_score,
            "json_errors": json_error,
            "domain_coverage": domain_coverage,
            "sample_entities": entities_extracted[:6],
            "sample_relations": relations_extracted[:4]
        }

        results.append(chunk_record)

        print(f"    --> Time: {elapsed:.2f}s | Success: {chunk_record['success']} | Valid LightRAG: {chunk_record['valid_lightrag_output']}")
        print(f"    --> Nodes: {len(nodes_dict)}, Edges: {len(edges_dict)} | Quality: {quality_score}")
        print(f"    --> CPU: {cpu_used}% | System RAM: {sys_ram_after}%")
        if json_error:
            print(f"    --> JSON Error: {json_error}")
        matched_domains = [k for k, v in domain_coverage.items() if v]
        print(f"    --> Domain Matches ({len(matched_domains)}): {matched_domains}")

        # Save progress after every chunk
        interim_data = {
            "status": "IN_PROGRESS" if idx < total_chunks else "COMPLETED",
            "completed_chunks": idx,
            "total_chunks": total_chunks,
            "results": results
        }
        with open(WORKING_DIR / "benchmark_results.json", "w", encoding="utf-8") as f:
            json.dump(interim_data, f, indent=2)

    total_time = time.time() - benchmark_start_time
    times = [r["extraction_time_s"] for r in results if r["extraction_time_s"] > 0]
    avg_time = sum(times) / len(times) if times else 0
    median_time = sorted(times)[len(times)//2] if times else 0
    min_time = min(times) if times else 0
    max_time = max(times) if times else 0

    # Calculate remaining documents estimation
    with open(WORKING_DIR / "doc_status_categorized.json", "r", encoding="utf-8") as f:
        doc_cat = json.load(f)
    failed_docs = doc_cat["failed"]
    total_remaining_chunks = sum(d.get("chunks_count", 0) for d in failed_docs)
    # Plus the 1 processing doc
    processing_docs = doc_cat["processing"]
    total_remaining_chunks += sum(d.get("chunks_count", 0) for d in processing_docs)
    # Also files with 0 chunks that need parsing might produce ~3 chunks each on average
    zero_chunk_docs = sum(1 for d in failed_docs if d.get("chunks_count", 0) == 0)
    avg_chunks_per_doc = 3.0
    estimated_total_chunks = total_remaining_chunks + (zero_chunk_docs * avg_chunks_per_doc)

    est_total_seconds = estimated_total_chunks * avg_time
    est_hours = est_total_seconds / 3600

    summary = {
        "benchmark_completed": True,
        "total_chunks_benchmarked": len(results),
        "total_wall_time_s": round(total_time, 2),
        "avg_time_per_chunk_s": round(avg_time, 2),
        "median_time_per_chunk_s": round(median_time, 2),
        "min_time_s": round(min_time, 2),
        "max_time_s": round(max_time, 2),
        "total_waiting_documents": len(failed_docs) + len(processing_docs),
        "recorded_chunks_waiting": total_remaining_chunks,
        "zero_chunk_docs_pending_parse": zero_chunk_docs,
        "estimated_total_chunks_remaining": round(estimated_total_chunks, 1),
        "estimated_total_processing_seconds": round(est_total_seconds, 1),
        "estimated_total_processing_hours": round(est_hours, 2),
        "results": results
    }

    with open(WORKING_DIR / "benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("\n" + "=" * 80)
    print("BENCHMARK COMPLETED SUCCESSFULLY!")
    print(f"Avg time per chunk: {avg_time:.2f}s | Median: {median_time:.2f}s")
    print(f"Estimated chunks remaining: {estimated_total_chunks:.1f}")
    print(f"Estimated time for remaining 82 documents: {est_hours:.2f} hours ({est_total_seconds/60:.1f} minutes)")
    print("=" * 80)

if __name__ == "__main__":
    run_benchmark()
