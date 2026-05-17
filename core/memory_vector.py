"""
MemoryVectorStore — ChromaDB-backed vector store for agent semantic memory.

Reuses the embedding function configuration from plugins/server/vector_kb.py.
Each agent's memories are stored in one ChromaDB collection with agent_name metadata.
"""
import os
from pathlib import Path
from core.config import CFG
from core.logger import log


class MemoryVectorStore:
    """Vector store for agent memory, backed by ChromaDB."""

    def __init__(self, persist_dir: str | None = None):
        if persist_dir is None:
            persist_dir = str(CFG.DATA / "chroma_memory")
        self._persist_dir = persist_dir
        Path(persist_dir).mkdir(parents=True, exist_ok=True)
        self._collection = None  # lazy init

    def _ensure_collection(self):
        if self._collection is None:
            import chromadb
            from plugins.server.vector_kb import _get_embedding_function
            client = chromadb.PersistentClient(path=self._persist_dir)
            ef = _get_embedding_function()
            self._collection = client.get_or_create_collection(
                name="agent_memory",
                embedding_function=ef,
                metadata={"hnsw:space": "cosine"},
            )

    def add(self, agent_name: str, text: str, metadata: dict | None = None) -> str:
        """Add text to vector store. Returns a synthetic doc_id."""
        self._ensure_collection()
        meta = metadata or {}
        meta["agent_name"] = agent_name
        import uuid
        doc_id = f"{agent_name}:{uuid.uuid4().hex[:12]}"
        self._collection.add(documents=[text], metadatas=[meta], ids=[doc_id])
        log.debug(f"MemoryVector: added '{doc_id}' for agent '{agent_name}'")
        return doc_id

    def query(self, agent_name: str, query: str, top_k: int = 5) -> list[dict]:
        """Semantic search within agent_name's memories."""
        self._ensure_collection()
        results = self._collection.query(
            query_texts=[query],
            n_results=top_k,
            where={"agent_name": agent_name},
            include=["documents", "metadatas", "distances"],
        )
        items = []
        if results.get("ids") and results["ids"][0]:
            for i in range(len(results["ids"][0])):
                items.append({
                    "content": results["documents"][0][i] if results.get("documents") else "",
                    "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
                    "distance": results["distances"][0][i] if results.get("distances") else 0,
                    "id": results["ids"][0][i],
                })
        return items

    def delete_agent(self, agent_name: str) -> int:
        """Remove all vectors for an agent. Returns count removed."""
        self._ensure_collection()
        results = self._collection.get(where={"agent_name": agent_name}, include=[])
        if results.get("ids"):
            self._collection.delete(ids=results["ids"])
            count = len(results["ids"])
            log.info(f"MemoryVector: deleted {count} vectors for '{agent_name}'")
            return count
        return 0

    def stats(self) -> dict:
        """Return total count and per-agent breakdown."""
        self._ensure_collection()
        total = self._collection.count()
        return {"total_vectors": total}
