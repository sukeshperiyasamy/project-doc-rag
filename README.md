# Project Doc-RAG: Personal Research Knowledge Base

An offline-first, privacy-preserving Graph-Augmented Retrieval (Graph-RAG) system engineered for deep scientific and experimental document analysis.

---

## 🏛️ System Architecture

The core architecture follows a decoupled, privacy-centric pipeline:

```
[ Research Corpus ]
        │
        ▼ (Read-Only Copy & SHA256 Sync)
[ Local Staging: inputs/ ]
        │
        ▼
   [ LightRAG ]
        ├──► Local FastEmbed Engine (Port 9622: BAAI/bge-small-en-v1.5, ONNX CPU)
        ├──► Structured Entity/Relation Extraction (Ollama qwen2.5:3b / LLM)
        │         └─ Domain Schema: Biomarkers, Raman Peaks, Substrates, SOPs, Concentrations
        ▼
[ Knowledge Graph & Vector Store ]
        ├── NetworkX Graph (`graph_chunk_entity_relation.graphml`)
        ├── NanoVectorDB Storage (`vdb_chunks.json`, `vdb_entities.json`)
        └── JsonKV Storage (`kv_store_*.json`)
        │
        ▼
[ Dual Query & Exploration Interface ]
        ├── Interactive Web UI & Graph Visualizer (`http://127.0.0.1:9621`)
        └── CLI Query Engine (`scripts/query_cli.py`)
```

### Key Components

1. **LightRAG Core Engine**: Coordinates semantic chunking, dual-level vectorization (chunk + entity level), graph relation linking, and multi-hop hybrid retrieval.
2. **Local FastEmbed Embedding Server (`scripts/local_embedding_server.py`)**:
   - Ultra-fast ONNX runtime serving `BAAI/bge-small-en-v1.5` (384-dimensional dense vectors).
   - OpenAI-compatible HTTP endpoint strictly bound to `http://127.0.0.1:9622`.
   - 100% offline, zero cloud API call or token cost for embeddings.
3. **Structured Research Knowledge Graph Extraction**:
   - Guided by custom domain ontology definitions (`config/entity_type_prompt.yml`).
   - Extracts structured entities: `Biomarker` (NAM, LPS, LTA), `Substrate` (Black Silicon, etched Si), `Instrument_Parameter` (785 nm, laser power), `Spectral_Peak` (wavenumbers, Raman shifts), `Concentration`, `Measurement`, `Method_Protocol`, and `Problem_Cause`.
4. **Safe Staging & Sync Pipeline (`scripts/sync_and_index.py`)**:
   - Treats research source drives/directories as **strictly read-only**.
   - Computes SHA-256 hashes to prevent re-indexing unchanged documents.
   - Automatically filters out incompatible file formats while preserving DOCX tables/equations, PDFs, and Markdown.

---

## 🔒 Security & Privacy Guarantees

- **No Secrets in Version Control**: `.env` and `config/.env` are strictly excluded via `.gitignore`.
- **Private Research Corpus**: Raw PDFs, DOCX files, laboratory worksheets, and proprietary data in `inputs/` and `mtp/` are excluded.
- **Local Storage Isolation**: Graph databases, vector stores, and KV caches in `rag_storage/` remain local only.
- **Local Fallbacks**: Full support for local execution via Ollama (`qwen2.5:3b`) and local FastEmbed embeddings.

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.10+
- [Ollama](https://ollama.ai) (optional for local LLM inference)

### 2. Environment Configuration
Copy the template configuration file:
```bash
cp config/.env.example config/.env
```
Edit `config/.env` to configure your preferred LLM binding (e.g. `ollama` or API provider).

### 3. Start Local Embedding Server
```powershell
python scripts/local_embedding_server.py
```
Health check:
```bash
curl http://127.0.0.1:9622/health
# Response: {"status":"ok","model":"bge-small-en-v1.5","dim":384}
```

### 4. Start LightRAG Server
Run the startup script:
```powershell
.\scripts\start_server.ps1
```
The Web UI will be available at:
- Web UI: `http://127.0.0.1:9621/webui`
- Interactive Workspace: `http://127.0.0.1:9621/workspace`

### 5. Staging & Synchronizing Documents
To stage and index documents from your research directory:
```powershell
# Check current sync status
python scripts/sync_and_index.py --status

# Stage representative subset
python scripts/sync_and_index.py --test-subset --index

# Stage all supported documents
python scripts/sync_and_index.py --all --index
```

### 6. Querying the Knowledge Base via CLI
```powershell
python scripts/query_cli.py --mode hybrid --query "What Raman peaks are diagnostic for NAM detection on Black Silicon?"
```
Modes available: `hybrid`, `local`, `global`, `naive`.
