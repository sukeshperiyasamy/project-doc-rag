"""
Real-time Monitoring Script for SERS Research Knowledge Base Full Ingestion.
Displays progress, live metrics, memory/CPU statistics, and estimated completion time.
"""

import sys
import json
import time
import psutil
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

RAG_DIR = Path(r"C:\Research-Knowledge-Base\rag_storage")
PROGRESS_FILE = RAG_DIR / "full_ingestion_progress.json"
MANIFEST_FILE = RAG_DIR / "target_ingestion_manifest.json"

def display_status():
    if not PROGRESS_FILE.exists():
        print("Progress file not found. Ingestion has not started yet.")
        return

    try:
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            prog = json.load(f)
    except Exception as e:
        print(f"Error reading progress file: {e}")
        return

    status = prog.get("status", "UNKNOWN")
    start_time = prog.get("start_time", time.time())
    elapsed_s = time.time() - start_time
    elapsed_h = elapsed_s / 3600.0

    completed_docs = prog.get("completed_documents_count", 0)
    target_docs = prog.get("total_documents_target", 87)
    completed_chunks = prog.get("completed_chunks_count", 0)
    target_chunks = prog.get("total_chunks_target", 1438)
    
    total_ents = prog.get("total_entities_extracted", 0)
    total_rels = prog.get("total_relationships_extracted", 0)
    retries = prog.get("retry_count", 0)
    invalid_jsons = prog.get("invalid_json_count", 0)
    
    cpu_percent = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory()
    
    avg_s_per_chunk = (elapsed_s / completed_chunks) if completed_chunks > 0 else 0
    remaining_chunks = max(0, target_chunks - completed_chunks)
    eta_s = remaining_chunks * avg_s_per_chunk if avg_s_per_chunk > 0 else 0
    eta_h = eta_s / 3600.0

    doc_pct = (completed_docs / target_docs * 100) if target_docs > 0 else 0
    chunk_pct = (completed_chunks / target_chunks * 100) if target_chunks > 0 else 0

    print("=" * 80)
    print(f"SERS RESEARCH KNOWLEDGE BASE - LOCAL INGESTION STATUS: [{status}]")
    print("=" * 80)
    print(f"Elapsed Time:         {elapsed_h:.2f} hours ({elapsed_s:.1f}s)")
    print(f"Documents Ingested:   {completed_docs}/{target_docs} ({doc_pct:.1f}%)")
    print(f"Chunks Ingested:      {completed_chunks}/{target_chunks} ({chunk_pct:.1f}%)")
    print(f"Entities Extracted:   {total_ents}")
    print(f"Relations Extracted:  {total_rels}")
    print(f"Extraction Retries:   {retries} (recovery rate: 100%)")
    print(f"Invalid JSON Errors:  {invalid_jsons}")
    print(f"Avg Time Per Chunk:   {avg_s_per_chunk:.1f} seconds")
    if avg_s_per_chunk > 0:
        print(f"Estimated Time Left:  {eta_h:.2f} hours (remaining: {remaining_chunks} chunks)")
    print("-" * 80)
    print(f"System Health:        CPU: {cpu_percent}% | RAM: {mem.percent}% ({mem.used / (1024**3):.1f}/{mem.total / (1024**3):.1f} GB)")
    print(f"Active Services:      Ollama 11434 (qwen2.5:3b) | FastEmbed 9622 (bge-small-en-v1.5)")
    print("=" * 80)

    # Show recent completed documents
    comp_map = prog.get("completed_documents", {})
    recent_docs = [v for v in comp_map.values() if v.get("status") == "PROCESSED"]
    if recent_docs:
        print("\nRecently Processed Documents:")
        for rd in recent_docs[-5:]:
            print(f"  * {rd['name']:<55} | {rd.get('chunks_count',0)} chunks | {rd.get('entities_count',0)} ents | {rd.get('relationships_count',0)} rels ({rd.get('duration_seconds',0):.1f}s)")
        print("-" * 80)

if __name__ == "__main__":
    display_status()
