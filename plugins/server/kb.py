"""
kb.py — 知识库引擎 (关键词 + 向量混合模式)
=============================================
支持两种模式:
  - keyword: 传统关键词匹配 (轻量)
  - hybrid:  关键词 + ChromaDB 向量检索 (推荐)

环境变量:
  KB_MODE=keyword|hybrid      (默认: hybrid)
  VECTOR_KB_PATH=存储路径     (默认: data/chroma_db)
"""

import hashlib
import math
from collections import Counter
from pathlib import Path
from core.config import CFG


class KnowledgeBase:
    """
    知识库引擎，支持关键词 + 向量混合检索。
    """
    def __init__(self, docs_dir=None, mode=None):
        self.docs_dir = Path(docs_dir or "data/docs")
        self.docs_dir.mkdir(parents=True, exist_ok=True)
        self.engine_name = "hybrid_kb"
        # mode: keyword | vector | hybrid
        self.mode = mode or CFG.KB_MODE
        self.all_chunks = []
        self._doc_mtimes: dict[str, float] = {}  # filepath -> last modified time
        self._last_scan = 0
        self._vector_kb = None

        # 初始化向量引擎（如果启用）
        if self.mode in ("vector", "hybrid"):
            try:
                from plugins.server.vector_kb import VectorKnowledgeBase
                self._vector_kb = VectorKnowledgeBase(docs_dir=str(self.docs_dir))
                self.engine_name = f"hybrid_kb+{self._vector_kb.engine_name}"
            except Exception as e:
                if CFG.DEBUG:
                    print(f"  [KB] Vector engine unavailable: {e}")
                self.mode = "keyword" if self.mode == "hybrid" else self.mode

    def watch(self, interval=30):
        """Initial full scan; subsequent calls should use incremental via _scan(incremental=True)."""
        self._scan(incremental=False)

    def _scan(self, incremental=True):
        """Scan docs directory. When incremental=True, skip files with unchanged mtime."""
        if incremental and not self.all_chunks:
            incremental = False  # First run must be full scan

        new_files: list[Path] = []
        changed_files: list[Path] = []
        current_files: set[str] = set()

        for f in sorted(self.docs_dir.glob("**/*")):
            if not f.is_file():
                continue
            ext = f.suffix.lower()
            supported = {".txt", ".md", ".json", ".yaml", ".yml", ".pdf", ".docx", ".py"}
            if ext not in supported:
                continue
            fkey = str(f)
            current_files.add(fkey)
            mtime = f.stat().st_mtime

            if incremental and fkey in self._doc_mtimes:
                if mtime == self._doc_mtimes[fkey]:
                    continue  # Unchanged — skip
                changed_files.append(f)
            else:
                new_files.append(f)
            self._doc_mtimes[fkey] = mtime

        # Remove entries for deleted files
        for fkey in list(self._doc_mtimes.keys()):
            if fkey not in current_files:
                del self._doc_mtimes[fkey]

        affected = new_files + changed_files
        if not affected and incremental:
            return  # Nothing changed

        # If full scan or new/changed files, rebuild chunk index
        if not incremental:
            self.all_chunks = []

        # Remove old chunks from changed/deleted files
        affected_keys = {str(p) for p in affected}
        if incremental:
            self.all_chunks = [c for c in self.all_chunks if c["filepath"] not in affected_keys]

        for f in affected:
            try:
                ext = f.suffix.lower()
                if ext == ".pdf":
                    content = self._read_pdf(f)
                elif ext == ".docx":
                    content = self._read_docx(f)
                else:
                    content = f.read_text(encoding="utf-8", errors="replace")
                if not content:
                    continue
                doc_id = hashlib.md5(str(f).encode()).hexdigest()[:12]
                paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
                for i, para in enumerate(paragraphs):
                    if len(para) < 10:
                        continue
                    self.all_chunks.append({
                        "id": f"{doc_id}_{i}",
                        "filepath": str(f),
                        "filename": f.name,
                        "content": para,
                    })
            except Exception as e:
                print(f"  [KB] Skip {f.name}: {e}")

        self._build_tfidf_index()

    def query(self, question, top_k=5):
        """
        查询知识库 (自动选择模式)。
        
        Args:
            question: 查询问题
            top_k: 返回结果数
            
        Returns:
            dict: has_result, sources, engine, token_cost, context
        """
        if not question:
            return self._empty_result()

        # 向量模式：优先使用向量检索
        if self.mode in ("vector", "hybrid") and self._vector_kb:
            result = self._vector_kb.query(question, top_k=top_k)
            if result.get("has_result"):
                return result
            # hybrid: 向量无结果则回退到关键词
            if self.mode == "vector":
                return result

        # 关键词模式
        return self._keyword_query(question, top_k)

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text: CJK characters individually, ASCII words as-is (min 2 chars)."""
        tokens: list[str] = []
        buf = ""
        for ch in text:
            if '一' <= ch <= '鿿' or '㐀' <= ch <= '䶿' or '豈' <= ch <= '﫿':
                if buf:
                    t = buf.strip().lower()
                    if len(t) > 1:
                        tokens.append(t)
                    buf = ""
                tokens.append(ch.lower())
            elif ch.isalnum():
                buf += ch
            else:
                if buf:
                    t = buf.strip().lower()
                    if len(t) > 1:
                        tokens.append(t)
                    buf = ""
        if buf:
            t = buf.strip().lower()
            if len(t) > 1:
                tokens.append(t)
        return tokens

    def _build_tfidf_index(self):
        """Build TF-IDF vectors for all chunks. Call after _scan()."""
        self._idf: dict[str, float] = {}
        self._chunk_vecs: list[dict[str, float]] = []
        N = len(self.all_chunks)
        if N == 0:
            return

        # Compute document frequency
        df: Counter[str] = Counter()
        all_tokens: list[Counter[str]] = []
        for chunk in self.all_chunks:
            tokens = Counter(self._tokenize(chunk["content"]))
            all_tokens.append(tokens)
            for t in tokens:
                df[t] += 1

        # IDF
        self._idf = {t: math.log((N + 1) / (df[t] + 1)) + 1.0 for t in df}

        # Normalized TF-IDF vectors
        self._chunk_vecs = []
        for tokens in all_tokens:
            total = sum(tokens.values()) or 1
            vec = {t: (count / total) * self._idf.get(t, 0) for t, count in tokens.items()}
            norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
            self._chunk_vecs.append({t: v / norm for t, v in vec.items()})

    def _keyword_query(self, question, top_k=5):
        """TF-IDF cosine similarity query."""
        if not self.all_chunks:
            return self._empty_result()

        # Rebuild index if needed
        if not hasattr(self, '_chunk_vecs') or len(self._chunk_vecs) != len(self.all_chunks):
            self._build_tfidf_index()

        # Build query vector
        q_tokens = self._tokenize(question)
        if not q_tokens:
            return self._empty_result()
        q_counts = Counter(q_tokens)
        total_q = sum(q_counts.values())
        q_vec = {t: (c / total_q) * self._idf.get(t, 0) for t, c in q_counts.items()}
        q_norm = math.sqrt(sum(v * v for v in q_vec.values())) or 1.0
        q_vec = {t: v / q_norm for t, v in q_vec.items()}

        # Cosine similarity
        scores: list[tuple[float, int]] = []
        for i, cvec in enumerate(self._chunk_vecs):
            dot = sum(v * cvec.get(t, 0) for t, v in q_vec.items())
            if dot > 0:
                scores.append((dot, i))

        scores.sort(key=lambda x: -x[0])
        top = scores[:top_k]

        if not top:
            return self._empty_result()

        sources: list[str] = []
        context_parts: list[str] = []
        for score, idx in top:
            chunk = self.all_chunks[idx]
            sources.append(chunk["filename"])
            context_parts.append(f"[来源: {chunk['filename']} | 相关度: {score:.3f}]\n{chunk['content']}")

        context = "\n\n---\n\n".join(context_parts)
        return {
            "has_result": True,
            "sources": list(set(sources)),
            "engine": self.engine_name,
            "token_cost": len(context) // 4,
            "context": context,
        }

    def add_text(self, text: str, filename: str = "memory.txt") -> dict:
        """直接添加文本到知识库"""
        if self._vector_kb:
            return self._vector_kb.add_text(text, filename)
        fp = self.docs_dir / filename
        with open(fp, "a", encoding="utf-8") as f:
            f.write(f"\n\n{text}")
        # Force non-incremental to pick up the new/updated file
        self._scan(incremental=False)
        return {"added": 1, "filename": filename}

    def stats(self) -> dict:
        """获取知识库统计"""
        if self._vector_kb:
            return self._vector_kb.stats()
        return {
            "enabled": True,
            "engine": self.engine_name,
            "documents": len(self.all_chunks),
            "mode": self.mode,
        }

    def refresh(self):
        """强制刷新"""
        self._scan()
        if self._vector_kb:
            self._vector_kb.refresh()

    def _read_pdf(self, filepath: Path) -> str:
        """Extract text from PDF (requires PyPDF2 or pdfplumber)."""
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(str(filepath))
            texts = []
            for page in reader.pages[:50]:
                t = page.extract_text()
                if t:
                    texts.append(t)
            return "\n\n".join(texts)
        except ImportError:
            pass
        try:
            import pdfplumber
            with pdfplumber.open(str(filepath)) as pdf:
                return "\n\n".join(p.extract_text() or "" for p in pdf.pages[:50])
        except ImportError:
            return ""

    def _read_docx(self, filepath: Path) -> str:
        """Extract text from DOCX (requires python-docx)."""
        try:
            from docx import Document
            doc = Document(str(filepath))
            return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except ImportError:
            return ""

    def _empty_result(self):
        return {
            "has_result": False, "sources": [],
            "engine": self.engine_name, "token_cost": 0, "context": "",
        }
