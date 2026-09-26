import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastembed import TextEmbedding
import numpy as np

app = FastAPI(title="Local FastEmbed OpenAI-Compatible Embedding Server")

# Load lightweight local model (BAAI/bge-small-en-v1.5, 384 dim, ONNX CPU)
print("Loading local ONNX embedding model BAAI/bge-small-en-v1.5...")
model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
print("Local embedding model loaded successfully!")

@app.get("/health")
@app.get("/v1/models")
async def health():
    return {"status": "ok", "model": "bge-small-en-v1.5", "dim": 384}

@app.post("/v1/embeddings")
@app.post("/embeddings")
async def create_embeddings(request: Request):
    body = await request.json()
    inp = body.get("input", [])
    if isinstance(inp, str):
        texts = [inp]
    elif isinstance(inp, list):
        texts = [str(x) for x in inp]
    else:
        texts = [str(inp)]

    # Compute local embeddings via ONNX
    raw_embeddings = list(model.embed(texts))
    
    data = []
    for idx, emb in enumerate(raw_embeddings):
        vec = np.array(emb, dtype=np.float32)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        data.append({
            "object": "embedding",
            "index": idx,
            "embedding": vec.tolist(),
        })

    return JSONResponse({
        "object": "list",
        "data": data,
        "model": body.get("model", "bge-small-en-v1.5"),
        "usage": {
            "prompt_tokens": sum(len(t.split()) for t in texts),
            "total_tokens": sum(len(t.split()) for t in texts),
        }
    })

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=9622, log_level="info")
