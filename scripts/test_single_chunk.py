import os
import sys
import json
import time
import psutil
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

os.environ["PROMPT_DIR"] = "C:/Research-Knowledge-Base/config"
from lightrag.prompt import PROMPTS, resolve_entity_extraction_prompt_profile
from lightrag.operate import _process_json_extraction_result
from lightrag.utils import tolerant_load_json_dict
import ollama

# Load prompt profile
prof = resolve_entity_extraction_prompt_profile(
    {"entity_type_prompt_file": "entity_type_prompt.yml"},
    use_json=True
)

entity_types_guidance = prof["entity_types_guidance"]
examples = "\n".join(prof["entity_extraction_json_examples"])
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

with open(Path(r"C:\Research-Knowledge-Base\rag_storage\selected_10_benchmark_candidates.json"), "r", encoding="utf-8") as f:
    candidates = json.load(f)

test_item = candidates[0]
print(f"Testing chunk from {test_item['filename']} ({test_item['category']})")
print(f"Chunk ID: {test_item['chunk_id']}, length: {len(test_item['content'])} chars")

user_prompt = PROMPTS["entity_extraction_json_user_prompt"].format(
    entity_types_guidance=entity_types_guidance,
    heading_context_block="",
    input_text=test_item["content"],
    language=language,
    max_total_records=max_total_records,
    max_entity_records=max_entity_records,
)

proc = psutil.Process()
cpu_start = psutil.cpu_percent(interval=None)
ram_start = proc.memory_info().rss / (1024 * 1024)

start_time = time.time()
print("Calling Ollama qwen2.5:3b with format='json'...")
response = ollama.chat(
    model="qwen2.5:3b",
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ],
    format="json",
    options={"temperature": 0.0}
)
elapsed = time.time() - start_time
cpu_end = psutil.cpu_percent(interval=None)
ram_end = proc.memory_info().rss / (1024 * 1024)
sys_ram = psutil.virtual_memory().percent

raw_output = response["message"]["content"]
print(f"\nElapsed time: {elapsed:.2f}s")
print(f"RAM before: {ram_start:.1f} MB, after: {ram_end:.1f} MB (System RAM: {sys_ram}%)")
print(f"Raw output length: {len(raw_output)} chars")

parsed = tolerant_load_json_dict(raw_output)
if parsed:
    entities = parsed.get("entities", [])
    relationships = parsed.get("relationships", [])
    print(f"\nSuccessfully parsed JSON!")
    print(f"Entities found: {len(entities)}")
    print(f"Relationships found: {len(relationships)}")
    for e in entities[:5]:
        print(f"  * Entity: {e.get('name')} | Type: {e.get('type')} | Desc: {e.get('description')}")
    for r in relationships[:5]:
        print(f"  * Relation: {r.get('source')} -> {r.get('target')} | Desc: {r.get('description')}")
else:
    print("\nFailed to parse JSON!")
    print(raw_output[:500])
