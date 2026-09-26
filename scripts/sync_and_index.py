"""
Safe Incremental Synchronization & Ingestion Pipeline for Personal Research Knowledge Base.
Treats source folder as STRICTLY READ-ONLY. Copies new/modified files to local staging (inputs/)
and triggers LightRAG indexing.
"""

import os
import sys
import json
import shutil
import hashlib
import argparse
import urllib.request
import urllib.error
from pathlib import Path
from dotenv import load_dotenv

# Load configuration
BASE_DIR = Path(r"C:\Research-Knowledge-Base")
ENV_PATH = BASE_DIR / "config" / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
else:
    load_dotenv(BASE_DIR / ".env")

SOURCE_DIR = Path(os.getenv("RESEARCH_SOURCE_DIR", r"C:\Users\sukes\Downloads\mtp"))
INPUT_DIR = Path(os.getenv("INPUT_DIR", str(BASE_DIR / "inputs")))
WORKING_DIR = Path(os.getenv("WORKING_DIR", str(BASE_DIR / "rag_storage")))
MANIFEST_PATH = WORKING_DIR / "sync_manifest.json"

# Excel files are strictly excluded from indexing per system requirements
EXCLUDED_EXTENSIONS = {".xlsx", ".xls"}
SUPPORTED_EXTENSIONS = {".docx", ".pdf", ".csv", ".txt", ".md", ".pptx"}

TEST_SUBSET_FILES = [
    "Critical_Evaluation_Sensor_Strategy_NAM_LPS_LTA_Aug2026.docx",
    "Consolidated_Experimental_Report_AllSessions_v2.docx",
    "Comprehensive_Research_Progress_Report_Sepsis_SERS_Aug2026.docx",
    "Bacterial_Surface_Markers_Evidence_Dossier_Updated.pdf",
]

def calculate_sha256(filepath: Path) -> str:
    """Calculate SHA256 hash of a file without modifying or locking it."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()

def load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        try:
            with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_manifest(manifest: dict):
    WORKING_DIR.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

def get_source_files(filter_files: list[str] = None) -> list[Path]:
    if not SOURCE_DIR.exists():
        print(f"[ERROR] Source directory does not exist: {SOURCE_DIR}")
        return []
    
    files = []
    for item in SOURCE_DIR.iterdir():
        if item.is_file() and item.suffix.lower() in SUPPORTED_EXTENSIONS and item.suffix.lower() not in EXCLUDED_EXTENSIONS:
            if filter_files:
                if item.name in filter_files:
                    files.append(item)
            else:
                files.append(item)
    return sorted(files, key=lambda x: x.name)

def sync_files(files_to_sync: list[Path]) -> list[Path]:
    """Copy files to INPUT_DIR staging area safely without touching original."""
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest()
    synced = []

    for src in files_to_sync:
        file_hash = calculate_sha256(src)
        recorded = manifest.get(src.name)

        if recorded and recorded.get("sha256") == file_hash and recorded.get("status") == "PROCESSED":
            # Unchanged and already indexed
            continue

        dest = INPUT_DIR / src.name
        # Copy to staging (source is strictly read-only)
        shutil.copy2(src, dest)
        manifest[src.name] = {
            "source_path": str(src),
            "sha256": file_hash,
            "size_bytes": src.stat().st_size,
            "modified_time": src.stat().st_mtime,
            "status": "STAGED_FOR_INDEX"
        }
        synced.append(dest)
        print(f"[STAGED] {src.name} -> {dest}")

    save_manifest(manifest)
    return synced

def trigger_server_scan(server_url="http://127.0.0.1:9621"):
    """Trigger LightRAG server to scan INPUT_DIR and index staged documents."""
    req_url = f"{server_url}/documents/scan"
    print(f"[INDEXING] Triggering server scan at {req_url}...")
    try:
        req = urllib.request.Request(req_url, data=b"", headers={"User-Agent": "ResearchKB-Sync"}, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"[SERVER RESPONSE] {json.dumps(data, indent=2)}")
            return True
    except urllib.error.URLError as e:
        print(f"[NOTICE] LightRAG server is not actively running at {server_url}: {e}")
        print("You can start the server with scripts/start_server.ps1 or run python scripts/sync_and_index.py --direct")
        return False

def print_status():
    manifest = load_manifest()
    source_files = get_source_files()
    print("=" * 80)
    print(f"Research Knowledge Base Sync Status")
    print(f"Source Directory (READ-ONLY): {SOURCE_DIR}")
    print(f"Total supported documents in source: {len(source_files)}")
    print(f"Tracked in manifest: {len(manifest)}")
    print("=" * 80)
    for f in source_files:
        info = manifest.get(f.name, {})
        status = info.get("status", "NOT_INDEXED")
        print(f" - {f.name:<60} [{status}]")
    print("=" * 80)

def main():
    parser = argparse.ArgumentParser(description="Sync and index research documents safely.")
    parser.add_argument("--status", action="store_true", help="Show current sync & index status")
    parser.add_argument("--test-subset", action="store_true", help="Stage only the 5 representative test documents")
    parser.add_argument("--all", action="store_true", help="Stage all supported documents from source")
    parser.add_argument("--files", type=str, help="Comma-separated filenames to stage")
    parser.add_argument("--index", action="store_true", help="Trigger indexing after staging")
    args = parser.parse_args()

    if args.status:
        print_status()
        return

    selected_names = None
    if args.test_subset:
        selected_names = TEST_SUBSET_FILES
        print(f"[MODE] Selected 5-document test subset:")
        for name in selected_names:
            print(f"  * {name}")
    elif args.files:
        selected_names = [f.strip() for f in args.files.split(",") if f.strip()]
        print(f"[MODE] Selected {len(selected_names)} specific files.")
    elif args.all:
        print("[MODE] Selected ALL supported documents from source.")
    else:
        print("Please specify --test-subset, --all, --files <name>, or --status.")
        return

    files_to_process = get_source_files(selected_names)
    print(f"[INFO] Found {len(files_to_process)} matching documents in source folder.")
    synced = sync_files(files_to_process)
    print(f"[INFO] Staged {len(synced)} new or updated documents in {INPUT_DIR}.")

    if args.index or len(synced) > 0:
        trigger_server_scan()

if __name__ == "__main__":
    main()


