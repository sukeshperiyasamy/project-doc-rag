import os
import sys
import json
from pathlib import Path

WORKING_DIR = Path(r"C:\Research-Knowledge-Base\rag_storage")
CONFIG_DIR = Path(r"C:\Research-Knowledge-Base\config")
os.environ["PROMPT_DIR"] = str(CONFIG_DIR)

from lightrag.prompt import PROMPTS, resolve_entity_extraction_prompt_profile
import ollama

prof = resolve_entity_extraction_prompt_profile(
    {"entity_type_prompt_file": "entity_type_prompt.yml"},
    use_json=True
)

system_prompt = PROMPTS["entity_extraction_json_system_prompt"].format(
    entity_types_guidance=prof["entity_types_guidance"],
    examples=prof["entity_extraction_json_examples"][0],
    language="English",
    max_total_records=30,
    max_entity_records=20,
)

with open(WORKING_DIR / "selected_10_benchmark_candidates.json", "r", encoding="utf-8") as f:
    candidates = json.load(f)

c = candidates[0]
user_prompt = PROMPTS["entity_extraction_json_user_prompt"].format(
    entity_types_guidance=prof["entity_types_guidance"],
    heading_context_block="",
    input_text=c["content"],
    language="English",
    max_total_records=30,
    max_entity_records=20,
)

res = ollama.chat(
    model="qwen2.5:3b",
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ],
    format="json",
    options={"temperature": 0.0}
)

raw = res.get("message", {}).get("content", "")
print("RAW OUTPUT LENGTH:", len(raw))
print("RAW OUTPUT PREVIEW:\n", raw[:1000])
try:
    d = json.loads(raw)
    print("PARSED KEYS:", list(d.keys()))
    if "entities" in d:
        print("ENTITIES COUNT:", len(d["entities"]))
        print("FIRST ENTITY:", d["entities"][0] if d["entities"] else "EMPTY")
except Exception as e:
    print("JSON PARSE ERROR:", e)
