"""
vector_kb.py — ChromaDB 向量知识库引擎
========================================
支持语义搜索的向量知识库，可自动将文档分块并生成 embedding。

依赖: pip install chromadb
环境变量:
  VECTOR_KB_PATH=存储路径        (默认: data/chroma_db)
  EMBEDDING_MODEL=模型名         (默认: all-MiniLM-L6-v2)
     可选:
       all-MiniLM-L6-v2          — 英文轻量 (默认, 384d)
       bge-small-zh-v1.5         — 中文优化 (512d)
       bge-base-en-v1.5          — 英文大模型 (768d)
       paraphrase-multilingual   — 多语言 (384d)
"""

import time
import hashlib
from pathlib import Path
from core.config import CFG
from core.logger import log


def _get_embedding_function():
    """Load embedding function based on EMBEDDING_MODEL env var."""
    model_name = CFG.EMBEDDING_MODEL
    try:
        from chromadb.utils import embedding_functions
        if model_name == "all-MiniLM-L6-v2":
            return embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2")
        elif model_name == "bge-small-zh-v1.5":
            return embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="BAAI/bge-small-zh-v1.5")
        elif model_name == "bge-base-en-v1.5":
            return embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="BAAI/bge-base-en-v1.5")
        elif model_name == "paraphrase-multilingual":
            return embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        else:
            # Custom model name
            return embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=model_name)
    except ImportError:
        log.warn("sentence-transformers not installed, using ChromaDB default")
        return None  # ChromaDB uses its own default
    except Exception as e:
        log.warn(f"Embedding function load failed: {e}, using default")
        return None


class VectorKnowledgeBase:
    """基于 ChromaDB 的向量知识库 (可配置 Embedding 模型)"""

    def __init__(self, docs_dir: str = None, persist_dir: str = None):
        self.docs_dir = Path(docs_dir or str(CFG.DOCS))
        self.docs_dir.mkdir(parents=True, exist_ok=True)

        self.persist_dir = Path(persist_dir or CFG.VECTOR_KB_PATH)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        self._embedding_model = CFG.EMBEDDING_MODEL
        self.engine_name = f"chroma_vector ({self._embedding_model})"
        self.mode = "vector"
        self.collection = None
        self._client = None
        self._init_chroma()

    def _init_chroma(self):
        """初始化 ChromaDB 客户端和集合（使用可配置的 embedding 函数）"""
        try:
            import chromadb
            self._client = chromadb.PersistentClient(
                path=str(self.persist_dir))
            ef = _get_embedding_function()
            if ef:
                self.collection = self._client.get_or_create_collection(
                    name="riycol_kb",
                    embedding_function=ef,  # type: ignore[arg-type]
                    metadata={"hnsw:space": "cosine"}
                )
            else:
                self.collection = self._client.get_or_create_collection(
                    name="riycol_kb",
                    metadata={"hnsw:space": "cosine"}
                )
            log.info(f"ChromaDB initialized: {self.persist_dir} (model={self._embedding_model})")
        except ImportError:
            log.warn("ChromaDB not installed (pip install chromadb)")
            raise
        except Exception as e:
            log.error(f"ChromaDB init failed: {e}")
            raise

    def add_document(self, filepath: str, content: str = "") -> dict:
        """
        添加/更新文档到向量库。
        自动读取文件内容并分块。
        """
        if self.collection is None:
            return {"added": 0, "error": "Vector database not initialized"}

        fp = Path(filepath)
        if not fp.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        if not content:
            content = fp.read_text(encoding="utf-8", errors="replace")

        chunks = []
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        for para in paragraphs:
            if len(para) < 20:
                continue
            if len(para) > 500:
                sentences = [s.strip() for s in para.replace("。", "。\n").split("\n") if s.strip()]
                for sent in sentences:
                    if len(sent) >= 20:
                        chunks.append(sent)
            else:
                chunks.append(para)

        if not chunks:
            return {"added": 0, "error": "No valid chunks found"}

        doc_id = hashlib.md5(str(fp).encode()).hexdigest()[:12]
        ids = [f"{doc_id}_{i}" for i in range(len(chunks))]

        try:
            self.collection.delete(where={"doc_id": doc_id})
        except Exception:
            pass

        self.collection.add(
            documents=chunks,
            ids=ids,
            metadatas=[{
                "doc_id": doc_id,
                "filename": fp.name,
                "filepath": str(fp),
                "chunk_index": i,
                "added_at": time.time(),
            } for i in range(len(chunks))]
        )

        log.info(f"KB added: {fp.name} -> {len(chunks)} chunks")
        return {"added": len(chunks), "doc_id": doc_id, "filename": fp.name}

    def add_text(self, text: str = "", filename: str = "memory.txt") -> dict:
        """直接添加文本到向量库"""
        if self.collection is None:
            return {"added": 0, "error": "Vector database not initialized"}
        if not text:
            return {"added": 0, "error": "Empty text"}
        filepath = self.docs_dir / filename
        mode = "a" if filepath.exists() else "w"
        with open(filepath, mode, encoding="utf-8") as f:
            f.write(f"\n\n{text}")
        return self.add_document(str(filepath), text)

    def query(self, question: str, top_k: int = 5) -> dict:
        """
        向量检索，返回与 keyword KB 兼容的格式。
        
        Returns:
            has_result, sources, engine, token_cost, context
        """
        if self.collection is None or not question:
            return self._empty_result()

        try:
            results = self.collection.query(
                query_texts=[question],
                n_results=min(top_k, 20),
            )

            if not results["documents"] or not results["documents"][0]:
                return self._empty_result()

            sources = []
            context_parts = []
            for i, doc in enumerate(results["documents"][0]):
                meta = results["metadatas"][0][i] if results["metadatas"] else {}
                filename = meta.get("filename", "unknown")
                sources.append(filename)
                context_parts.append(
                    f"[来源: {filename} | 相关度: {results['distances'][0][i]:.3f}]\n{doc}"
                )

            context = "\n\n---\n\n".join(context_parts)
            return {
                "has_result": True,
                "sources": list(set(sources)),
                "engine": self.engine_name,
                "token_cost": len(context) // 4,
                "context": context,
                "distances": results["distances"][0] if results.get("distances") else [],
            }

        except Exception as e:
            log.error(f"Vector KB query error: {e}")
            return self._empty_result()

    def delete_document(self, filename: str) -> bool:
        """从向量库删除文档"""
        if self.collection is None:
            return False
        try:
            self.collection.delete(where={"filename": filename})
            log.info(f"KB deleted: {filename}")
            return True
        except Exception as e:
            log.error(f"KB delete error: {e}")
            return False

    def stats(self) -> dict:
        """获取向量库统计"""
        result = {"enabled": True, "engine": self.engine_name,
                    "documents": 0, "mode": self.mode}
        if self.collection is None:
            return result
        try:
            result["documents"] = self.collection.count()
        except Exception:
            pass
        return result

    def _empty_result(self):
        return {
            "has_result": False, "sources": [],
            "engine": self.engine_name, "token_cost": 0, "context": "",
        }

    def refresh(self):
        """刷新：重新扫描 docs 目录并索引"""
        self.watch()

    def watch(self, interval: int = 30):
        """
        扫描 docs 目录中受支持的文件并索引。

        Args:
            interval: 扫描间隔（秒），由外部定时器控制，方法本身只做单次扫描不循环。
                      默认30秒，与 kb.py 的定时调用保持一致。
        """
        if self.collection is None:
            return
        extensions = {".txt", ".md", ".json", ".py", ".yaml", ".yml"}
        for f in sorted(self.docs_dir.glob("**/*")):
            if not f.is_file() or f.suffix.lower() not in extensions:
                continue
            try:
                self.add_document(str(f))
            except Exception as e:
                log.warn(f"KB scan skip {f.name}: {e}")
