import json
import statistics

with open("rag_storage/local_optimized_benchmark_results.json", "r", encoding="utf-8") as f:
    data = json.load(f)

print(f"Status: {data.get('status')}")
print(f"Completed: {data.get('completed_chunks')}/{data.get('total_chunks')}")

results = data.get("results", [])
times = []
for r in results:
    times.append(r["extraction_time_s"])
    print(f"Chunk {r['chunk_number']:02d}: {r['filename'][:35]:<35} | {r['extraction_time_s']:6.1f}s | {r['entities_count']:2d} ents | {r['relationships_count']:2d} rels | valid={r['json_valid']} | retried={r['retried']}")

if times:
    print("-" * 75)
    print(f"Mean time: {statistics.mean(times):.1f}s | Median: {statistics.median(times):.1f}s | Min: {min(times):.1f}s | Max: {max(times):.1f}s")
    valid_count = sum(1 for r in results if r["json_valid"])
    print(f"JSON Validity: {valid_count}/{len(results)} ({valid_count/len(results)*100:.1f}%)")
    zero_ents = sum(1 for r in results if r["entities_count"] == 0)
    print(f"Empty extraction rate: {zero_ents}/{len(results)} ({zero_ents/len(results)*100:.1f}%)")
