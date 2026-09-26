import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

WORKING_DIR = Path(r"C:\Research-Knowledge-Base\rag_storage")
with open(WORKING_DIR / "selected_10_benchmark_candidates.json", "r", encoding="utf-8") as f:
    cands = json.load(f)

print(f"Total candidates: {len(cands)}")
for i, c in enumerate(cands):
    print(f"\n--- [{i+1}] {c['category']} ---")
    print(f"File: {c['filename']}")
    print(f"Chunk ID: {c['chunk_id']}")
    print(f"Chars: {len(c['content'])}, Words: {len(c['content'].split())}")
    print(f"Preview: {c['content'][:200].replace('\n', ' ')}...")
