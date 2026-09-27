import asyncio
from lightrag import LightRAG
from lightrag.api.config import get_config
from lightrag.api.lightrag_server import create_embedding_function_from_args
from lightrag.llm.ollama import ollama_model_complete

args = get_config()
ef = create_embedding_function_from_args(args, {})
rag = LightRAG(
    working_dir='rag_storage',
    llm_model_func=ollama_model_complete,
    llm_model_name='qwen2.5:3b',
    embedding_func=ef,
    chunk_token_size=500,
    chunk_overlap_token_size=60,
    entity_extract_max_gleaning=0,
    entity_extract_max_records=25,
    entity_extract_max_entities=20
)

async def check():
    await rag.doc_status.initialize()
    from lightrag.base import DocStatus
    docs = await rag.doc_status.get_docs_by_statuses([DocStatus.PROCESSED, DocStatus.FAILED, DocStatus.PROCESSING, DocStatus.PENDING])
    from collections import Counter
    counts = Counter(d.status.value if hasattr(d.status, 'value') else d.status for d in docs.values())
    print("Status counts from rag.doc_status:", counts)

if __name__ == "__main__":
    asyncio.run(check())
