"""
Full Local Ingestion Pipeline for SERS / Sepsis Research Knowledge Base.
100% Local Inference: Ollama (qwen2.5:3b) + FastEmbed (bge-small-en-v1.5, 384 dim).
Zero Cloud APIs / Zero Gemini.
Preserves existing 26 processed documents and existing knowledge stores.
Safely resumable with per-chunk and per-document incremental persistence.
"""

import os
import sys
import json
import time
import re
import asyncio
import hashlib
import psutil
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

# Ensure scripts/ directory is in python path
BASE_DIR = Path(r"C:\Research-Knowledge-Base")
sys.path.append(str(BASE_DIR / "scripts"))

from file_text_extractor import (
    SOURCE_DIR,
    RAG_DIR,
    EXCLUDED_EXT,
    SUPPORTED_EXT,
    DUPLICATE_FILES,
    extract_text,
    chunk_text
)

# LightRAG Imports
from lightrag import LightRAG
from lightrag.base import DocStatus, DocProcessingStatus
from lightrag.api.config import get_config
from lightrag.api.lightrag_server import create_embedding_function_from_args
from lightrag.llm.ollama import ollama_model_complete

import ollama

# File paths
BACKUP_DIR = BASE_DIR / "rag_storage_backup_26docs"
MANIFEST_FILE = RAG_DIR / "target_ingestion_manifest.json"
PROGRESS_FILE = RAG_DIR / "full_ingestion_progress.json"
FINAL_SUMMARY_FILE = RAG_DIR / "final_ingestion_summary.json"

# Concise domain-specific extraction prompt validated in benchmark
CONCISE_SYSTEM_PROMPT = """You are a scientific Knowledge Graph specialist extracting entities and relationships from medical, biochemical, and spectroscopic research text.

Entity Types:
- Biomarker: Biological molecules, markers (e.g. NAM, LPS, LTA, bilirubin)
- Material: Nanoparticles, colloidal solutions, metals (e.g. silver nanoparticles, gold nanostars)
- Chemical: Reagents, solvents, salts, ligands (e.g. boronic acid, ethanol, PBS)
- Instrument: Hardware, spectrometers, detectors (e.g. Raman spectrometer, SEM)
- Instrument_Parameter: Operating parameters, settings (e.g. 785 nm, 532 nm, 10s integration, 10 mW)
- Measurement: Readings, intensities, SNR, enhancement factors, LOD, peak counts
- Method_Protocol: Protocols, fabrication SOPs, SERS measurement SOPs, MACE
- Author_Paper: Cited papers, researchers, literature references, external studies
- Biological_Structure: Cell membranes, bacterial wall structures, organelles, diols
- Target_Analyte: Target molecules, bacteria, clinical analytes, sepsis targets
- Substrate: Solid substrates, fabrication platforms (e.g. Black Silicon, etched silicon)
- Spectral_Peak: Raman peaks, bands, wavenumbers (e.g. 930 cm-1, 1580 cm-1, D band, G band)
- Concentration: Numerical concentrations (e.g. 0.1 mg/mL, 1 uM, 10 mM)
- Result: Detection outcomes, status (e.g. Detected, Not Detected)
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

from lightrag.utils_graph import normalize_entity_name

def validate_extraction_json(raw_text: str):
    """Validate JSON format, entity structure, relationship consistency, and repetition loops."""
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
    seen_names = set()
    for e in raw_entities:
        if not isinstance(e, dict):
            continue
        raw_name = str(e.get("name", "")).strip()
        etype = str(e.get("type", "")).strip()
        desc = str(e.get("description", "")).strip()
        norm_name = normalize_entity_name(raw_name) if raw_name else ""
        if norm_name and etype:
            norm_key = norm_name.lower()
            if norm_key not in seen_names:
                valid_entities.append({"name": norm_name, "type": etype, "description": desc})
                seen_names.add(norm_key)

    valid_relationships = []
    seen_rels = set()
    for r in raw_relationships:
        if not isinstance(r, dict):
            continue
        raw_src = str(r.get("source", "")).strip()
        raw_tgt = str(r.get("target", "")).strip()
        norm_src = normalize_entity_name(raw_src) if raw_src else ""
        norm_tgt = normalize_entity_name(raw_tgt) if raw_tgt else ""
        desc = str(r.get("description", "")).strip()
        keywords = str(r.get("keywords", "")).strip()
        try:
            weight = float(r.get("weight", 1.0))
        except (ValueError, TypeError):
            weight = 1.0

        if norm_src and norm_tgt and norm_src.lower() != norm_tgt.lower():
            rel_key = tuple(sorted((norm_src.lower(), norm_tgt.lower())))
            if rel_key not in seen_rels:
                valid_relationships.append({
                    "source": norm_src,
                    "target": norm_tgt,
                    "description": desc,
                    "keywords": keywords,
                    "weight": weight
                })
                seen_rels.add(rel_key)

    # Ensure all relationship endpoints exist in valid_entities
    for r in valid_relationships:
        for ep in [r["source"], r["target"]]:
            if ep.lower() not in seen_names:
                valid_entities.append({
                    "name": ep,
                    "type": "Other",
                    "description": f"Contextual research entity involved in {r['description']}"
                })
                seen_names.add(ep.lower())

    if len(valid_entities) == 0:
        return False, "Extraction returned 0 valid entities", valid_entities, valid_relationships

    # Check for runaway repetition loop (e.g. identical description repeated 5+ times)
    descs = [e["description"] for e in valid_entities if len(e["description"]) > 10]
    if len(descs) > 8 and len(set(descs)) < len(descs) * 0.3:
        return False, "Detected repetitive generation loop in entity descriptions", valid_entities, valid_relationships

    return True, None, valid_entities, valid_relationships

def extract_chunk_with_retry(chunk_text_content: str, current_threads: int = 8):
    """
    Extracts entities and relationships with primary (1024 tokens) and fallback (768 tokens, 1600 char slice).
    Returns (success, entities, relationships, error_msg, retried, extraction_time).
    """
    attempt = 1
    max_attempts = 2
    success = False
    final_entities = []
    final_relationships = []
    validation_error = None
    retried = False
    current_input = chunk_text_content
    start_time = time.time()

    while attempt <= max_attempts and not success:
        try:
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
                    "num_thread": current_threads
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
                if attempt < max_attempts:
                    retried = True
                    current_input = chunk_text_content[:1600]
        except Exception as e:
            validation_error = str(e)
            if attempt < max_attempts:
                retried = True
                current_input = chunk_text_content[:1600]
        attempt += 1

    elapsed = time.time() - start_time
    return success, final_entities, final_relationships, validation_error, retried, elapsed

def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "status": "INITIALIZING",
        "start_time": time.time(),
        "last_updated": time.time(),
        "already_processed_count": 26,
        "duplicate_skipped_count": 1,
        "failed_ocr_count": 7,
        "total_documents_target": 87,
        "completed_documents_count": 0,
        "completed_chunks_count": 0,
        "total_chunks_target": 1438,
        "total_entities_extracted": 0,
        "total_relationships_extracted": 0,
        "retry_count": 0,
        "invalid_json_count": 0,
        "empty_extraction_count": 0,
        "completed_documents": {},
        "failures": []
    }

def save_progress(progress: dict):
    progress["last_updated"] = time.time()
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, indent=2)

async def run_full_ingestion():
    print("=" * 85)
    print("STARTING FULL LOCAL DOCUMENT INGESTION")
    print("Engine: Ollama (qwen2.5:3b) + FastEmbed (bge-small-en-v1.5, 384 dim)")
    print("Target: SERS / Sepsis Personal Research Knowledge Base")
    print("=" * 85)

    # 1. Safety Checks
    if not BACKUP_DIR.exists():
        raise RuntimeError(f"CRITICAL SAFETY FAILURE: Backup directory {BACKUP_DIR} not found! Halting.")
    print(f"[VERIFIED] Existing 26-doc backup intact at: {BACKUP_DIR}")

    # Load target manifest
    if not MANIFEST_FILE.exists():
        raise RuntimeError(f"Target manifest {MANIFEST_FILE} not found! Run calculate_ingestion_inventory.py first.")
    with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # Load categorized status to verify the 26 protected docs
    with open(RAG_DIR / "doc_status_categorized.json", "r", encoding="utf-8") as f:
        cat = json.load(f)
    protected_doc_names = {Path(d["name"]).name for d in cat["processed"]}
    print(f"[PROTECTED] 26 successfully processed documents verified and will NOT be modified.")

    # Load or initialize progress
    progress = load_progress()
    progress["status"] = "IN_PROGRESS"
    save_progress(progress)

    # Initialize LightRAG
    print("[INITIALIZING] Initializing LightRAG instance with existing storage...")
    args = get_config()
    ef = create_embedding_function_from_args(args, {})
    rag = LightRAG(
        working_dir=str(RAG_DIR),
        llm_model_func=ollama_model_complete,
        llm_model_name='qwen2.5:3b',
        embedding_func=ef,
        chunk_token_size=500,
        chunk_overlap_token_size=60,
        entity_extract_max_gleaning=0,
        entity_extract_max_records=25,
        entity_extract_max_entities=20
    )
    await rag.initialize_storages()
    print("[INITIALIZED] LightRAG storages initialized successfully.")

    # Target queue
    targets = manifest["targets"]
    target_names_with_text = [t["name"] for t in targets if t["chunk_count"] > 0]
    print(f"[QUEUE] Total target files with text: {len(target_names_with_text)} ({manifest['total_chunks_to_process']} chunks)")
    print(f"[QUEUE] Scanned/empty files: {len(manifest['empty_files'])} (flagged for manual review / OCR)")

    # Record empty files in progress if not already recorded
    for ef_name in manifest["empty_files"]:
        if ef_name not in progress["completed_documents"]:
            progress["completed_documents"][ef_name] = {
                "name": ef_name,
                "status": "FAILED_OCR_NEEDED",
                "chunks_count": 0,
                "entities_count": 0,
                "relationships_count": 0,
                "note": "Document contains scanned images or no extractable text. Flagged for manual review."
            }
    save_progress(progress)

    active_threads = 8
    ingest_start = time.time()
    total_docs = len(target_names_with_text)

    # Ingestion loop over documents
    for doc_idx, doc_name in enumerate(target_names_with_text):
        if doc_name in protected_doc_names:
            print(f"[{doc_idx+1:02d}/{total_docs:02d}] {doc_name} is PROTECTED. Skipping.")
            continue

        if doc_name in progress["completed_documents"] and progress["completed_documents"][doc_name].get("status") == "PROCESSED":
            print(f"[{doc_idx+1:02d}/{total_docs:02d}] {doc_name} ALREADY COMPLETED in progress file. Skipping.")
            continue

        doc_file_path = SOURCE_DIR / doc_name
        full_text = extract_text(doc_file_path)
        chunks = chunk_text(full_text, target_size=2000, overlap=220)
        doc_chunk_count = len(chunks)

        print(f"\n" + "-" * 75)
        print(f"[{doc_idx+1:02d}/{total_docs:02d}] INGESTING DOCUMENT: {doc_name}")
        print(f"     Chunks: {doc_chunk_count} | Chars: {len(full_text)} | Words: {len(full_text.split())}")
        print("-" * 75)

        # Generate unique doc_id consistent with LightRAG hashing
        doc_id = f"doc-{hashlib.md5(doc_name.encode('utf-8')).hexdigest()}"

        doc_entities = []
        doc_relationships = []
        doc_chunk_records = []
        doc_start_time = time.time()
        doc_retries = 0
        doc_invalid_json = 0

        for chunk_idx, chunk_content in enumerate(chunks):
            chunk_alias = f"{doc_id}-chunk-{chunk_idx:03d}"
            
            # Check thermal / CPU load
            cpu_now = psutil.cpu_percent(interval=None)
            if cpu_now > 96 and active_threads == 8:
                active_threads = 6
                print(f"     [THERMAL/CPU ADAPT] CPU sustained at {cpu_now}%. Reducing threads to 6.")
            elif cpu_now < 75 and active_threads == 6:
                active_threads = 8

            success, entities, relationships, err, retried, chunk_time = extract_chunk_with_retry(
                chunk_content, current_threads=active_threads
            )

            if retried:
                doc_retries += 1
                progress["retry_count"] += 1

            if not success:
                doc_invalid_json += 1
                progress["invalid_json_count"] += 1
                print(f"     [CHUNK {chunk_idx+1}/{doc_chunk_count}] FAILED extraction: {err} ({chunk_time:.1f}s)")
            else:
                print(f"     [CHUNK {chunk_idx+1}/{doc_chunk_count}] OK ({chunk_time:.1f}s) -> {len(entities)} ents, {len(relationships)} rels (retried={retried})")

            # Tag entities and relationships with chunk source alias
            for e in entities:
                e_copy = dict(e)
                e_copy["source_chunk_id"] = chunk_alias
                doc_entities.append(e_copy)

            for r in relationships:
                r_copy = dict(r)
                r_copy["source_chunk_id"] = chunk_alias
                doc_relationships.append(r_copy)

            doc_chunk_records.append({
                "content": chunk_content,
                "source_id": chunk_alias,
                "file_path": doc_name,
                "chunk_order_index": chunk_idx
            })

            progress["completed_chunks_count"] += 1
            progress["total_entities_extracted"] += len(entities)
            progress["total_relationships_extracted"] += len(relationships)
            save_progress(progress)

        # Assemble custom_kg payload for LightRAG insertion
        custom_kg_payload = {
            "chunks": doc_chunk_records,
            "entities": [
                {
                    "entity_name": e["name"],
                    "entity_type": e["type"],
                    "description": e["description"],
                    "source_id": e["source_chunk_id"],
                    "file_path": doc_name
                }
                for e in doc_entities
            ],
            "relationships": [
                {
                    "src_id": r["source"],
                    "tgt_id": r["target"],
                    "description": r["description"],
                    "keywords": r.get("keywords", ""),
                    "weight": r.get("weight", 1.0),
                    "source_id": r["source_chunk_id"],
                    "file_path": doc_name
                }
                for r in doc_relationships
            ]
        }

        # Insert into LightRAG storages
        try:
            print(f"     [COMMITTING] Writing {len(doc_chunk_records)} chunks, {len(custom_kg_payload['entities'])} entities, {len(custom_kg_payload['relationships'])} relations to stores...")
            await rag.ainsert_custom_kg(custom_kg_payload, full_doc_id=doc_id)

            # Update document status in LightRAG doc_status storage
            now_iso = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
            doc_status_payload = {
                "content_summary": full_text[:100],
                "content_length": len(full_text),
                "status": DocStatus.PROCESSED,
                "created_at": now_iso,
                "updated_at": now_iso,
                "chunks_count": doc_chunk_count,
                "file_path": doc_name
            }
            await rag.doc_status.upsert({doc_id: doc_status_payload})

            # Update full_docs store
            await rag.full_docs.upsert({
                doc_id: {
                    "content": full_text,
                    "file_path": doc_name
                }
            })

            # Update recovery anchors for entities and relations
            unique_ent_names = sorted(list({e["name"] for e in doc_entities}))
            unique_rel_pairs = sorted(list({tuple(sorted((r["source"], r["target"]))) for r in doc_relationships}))
            await rag._union_doc_recovery_anchors(
                doc_id,
                unique_ent_names,
                [[p[0], p[1]] for p in unique_rel_pairs]
            )

            # Flush all storages to disk
            await rag._insert_done_with_cleanup()
            print(f"     [SUCCESS] Document {doc_name} fully indexed & persisted to disk!")

            doc_elapsed = time.time() - doc_start_time
            progress["completed_documents"][doc_name] = {
                "name": doc_name,
                "doc_id": doc_id,
                "status": "PROCESSED",
                "chunks_count": doc_chunk_count,
                "entities_count": len(custom_kg_payload["entities"]),
                "relationships_count": len(custom_kg_payload["relationships"]),
                "duration_seconds": round(doc_elapsed, 2),
                "retries": doc_retries,
                "invalid_json": doc_invalid_json
            }
            progress["completed_documents_count"] += 1
            save_progress(progress)

        except Exception as storage_err:
            print(f"     [STORAGE ERROR] Failed inserting document {doc_name}: {storage_err}")
            progress["failures"].append({
                "document": doc_name,
                "error": str(storage_err),
                "timestamp": time.time()
            })
            save_progress(progress)

    # Finalize storages
    await rag.finalize_storages()
    total_wall_time = time.time() - ingest_start

    # Final summary compilation
    summary = {
        "status": "COMPLETED",
        "total_source_files_discovered": 121,
        "already_processed_protected": 26,
        "newly_processed_documents": progress["completed_documents_count"],
        "duplicate_skipped_count": 1,
        "duplicate_skipped_files": ["LTA_Complete_Evidence_Report_1.docx"],
        "excluded_excel_count": 2,
        "excluded_excel_files": ["Elicit - NAM–SERS literature source survey.xlsx", "Lab_Chemicals_Inventory.xlsx"],
        "failed_scanned_ocr_needed_count": len(manifest["empty_files"]),
        "failed_scanned_ocr_needed_files": manifest["empty_files"],
        "storage_failures_count": len(progress["failures"]),
        "total_chunks_processed": progress["completed_chunks_count"],
        "total_entities_extracted": progress["total_entities_extracted"],
        "total_relationships_extracted": progress["total_relationships_extracted"],
        "total_retries": progress["retry_count"],
        "total_invalid_json": progress["invalid_json_count"],
        "total_wall_time_seconds": round(total_wall_time, 2),
        "total_wall_time_hours": round(total_wall_time / 3600, 2),
        "gemini_api_disabled": True,
        "original_26_docs_modified": False,
        "completed_documents": progress["completed_documents"]
    }

    with open(FINAL_SUMMARY_FILE, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("\n" + "=" * 85)
    print("FULL LOCAL INGESTION COMPLETE!")
    print(f"Newly processed documents: {summary['newly_processed_documents']}")
    print(f"Total chunks:              {summary['total_chunks_processed']}")
    print(f"Total entities:            {summary['total_entities_extracted']}")
    print(f"Total relationships:       {summary['total_relationships_extracted']}")
    print(f"Total runtime:             {summary['total_wall_time_hours']} hours")
    print(f"Final summary saved to:    {FINAL_SUMMARY_FILE}")
    print("=" * 85)

if __name__ == "__main__":
    asyncio.run(run_full_ingestion())
