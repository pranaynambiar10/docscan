"""
RAG (Retrieval-Augmented Generation) engine for DocScan.

Pipeline:
  Upload  → extract text → chunk → embed (sentence-transformers) → store in ChromaDB
  Question → embed query → semantic search → top-K chunks → LLM → answer

Why this is better than sending full text:
  - LLM only sees the 3-5 most relevant paragraphs (not 100 pages)
  - Faster inference (smaller prompt)
  - Higher accuracy (no irrelevant noise confusing the model)
  - Works on huge PDFs that exceed any context window
"""

import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
try:
    import torch
    torch.set_num_threads(2)
except ImportError:
    pass
import hashlib
from typing import List, Tuple

# ChromaDB — local persistent vector store (no server needed)
import chromadb
from chromadb.config import Settings

# Sentence-Transformers — local embedding model (no API key, no internet needed)
from sentence_transformers import SentenceTransformer

# ── Configuration ──────────────────────────────────────────────────────────────
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

def _get_chroma_path():
    path = os.getenv("CHROMA_DB_PATH", "./chroma_db")
    abs_path = os.path.abspath(path)
    # On Windows, if running inside OneDrive, redirect to local AppData to prevent OneDrive file sync locking SQLite
    if "onedrive" in abs_path.lower():
        local_dir = os.path.join(os.environ.get("LOCALAPPDATA", "C:/"), "docscan_chroma_db")
        os.makedirs(local_dir, exist_ok=True)
        return local_dir
    return path

CHROMA_DB_PATH = _get_chroma_path()
EMBED_MODEL_NAME = os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2")
CHUNK_SIZE     = int(os.getenv("RAG_CHUNK_SIZE", "500"))   # chars per chunk
CHUNK_OVERLAP  = int(os.getenv("RAG_CHUNK_OVERLAP", "100"))
TOP_K          = int(os.getenv("RAG_TOP_K", "5"))          # chunks sent to LLM


class RAGEngine:
    """
    Local RAG pipeline using ChromaDB + sentence-transformers.
    No internet required. All processing stays on the company server.
    """

    def __init__(self):
        print(f"🔄 Loading embedding model: {EMBED_MODEL_NAME}")
        try:
            # Ultra-fast local loading (0.2s) without making slow network requests to HuggingFace
            self.embedder = SentenceTransformer(EMBED_MODEL_NAME, local_files_only=True)
        except Exception:
            self.embedder = SentenceTransformer(EMBED_MODEL_NAME)
        dim = self.embedder.get_embedding_dimension()
        print(f"✅ Embedding model loaded ({dim}d vectors)")

        # Persistent ChromaDB — survives server restarts
        self.chroma = chromadb.PersistentClient(
            path=CHROMA_DB_PATH,
            settings=Settings(anonymized_telemetry=False),
        )
        # One collection per document (keyed by doc_id)
        self._collections: dict = {}
        print(f"✅ ChromaDB initialized at: {CHROMA_DB_PATH}")

    # ── Public API ─────────────────────────────────────────────────────────────

    def index_document(self, doc_id: str, text: str, sections: list = None) -> int:
        """
        Chunk a document, embed each chunk, and store in ChromaDB with section metadata.
        Returns the number of chunks indexed.
        Call this once after text extraction during upload.
        """
        if not text or not text.strip():
            print(f"⚠️  No text content provided to index for doc: {doc_id}")
            return 0

        chunks = []
        metadatas = []

        if sections:
            # Section-aware chunking: preserves section boundaries and attaches page/section metadata
            global_chunk_idx = 0
            for sec in sections:
                sec_content = sec.get('content', '').strip()
                if not sec_content:
                    continue
                sec_chunks = self._chunk_text(sec_content)
                for sc in sec_chunks:
                    chunks.append(sc)
                    metadatas.append({
                        "doc_id": doc_id,
                        "chunk_index": global_chunk_idx,
                        "section_id": str(sec.get("section_id", "")),
                        "section_title": str(sec.get("section_title", "")),
                        "parent_title": str(sec.get("parent_title", "")),
                        "page_start": int(sec.get("page_start", 1)),
                        "page_end": int(sec.get("page_end", 1)),
                    })
                    global_chunk_idx += 1
        else:
            chunks = self._chunk_text(text)
            metadatas = [{"doc_id": doc_id, "chunk_index": i} for i in range(len(chunks))]

        if not chunks:
            print(f"⚠️  No chunks generated for doc: {doc_id}")
            return 0

        print(f"🧩 Split document '{doc_id}' into {len(chunks)} chunk(s). Storing in ChromaDB...")
        collection = self._get_or_create_collection(doc_id)

        # Embed all chunks in one batched call
        embeddings = self.embedder.encode(
            chunks,
            batch_size=32,
            show_progress_bar=False,
            normalize_embeddings=True,   # Cosine similarity via dot product
        ).tolist()

        # Upsert into ChromaDB
        col_safe_name = self._col_name(doc_id)
        ids = [f"{col_safe_name}_chunk_{i}" for i in range(len(chunks))]
        collection.upsert(
            ids=ids,
            documents=chunks,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        print(f"✅ Indexed {len(chunks)} chunks for doc: {doc_id}")
        return len(chunks)

    def retrieve_with_metadata(self, doc_id: str, question: str, top_k: int = TOP_K) -> List[dict]:
        """
        Semantically retrieve top-K most relevant chunks along with section metadata.
        Returns list of dicts: {'text': str, 'similarity': float, 'section_id': str, ...}
        """
        collection = self._get_collection(doc_id)
        if collection is None or collection.count() == 0:
            return []

        query_embedding = self.embedder.encode(
            [question],
            normalize_embeddings=True,
        ).tolist()

        n_results = min(top_k, collection.count())
        if n_results == 0:
            return []

        results = collection.query(
            query_embeddings=query_embedding,
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )

        chunks = results["documents"][0] if results["documents"] else []
        metas = results["metadatas"][0] if results.get("metadatas") else []
        distances = results["distances"][0] if results["distances"] else []

        items = []
        for i, (chunk, dist) in enumerate(zip(chunks, distances)):
            score = 1 - dist
            meta = metas[i] if i < len(metas) else {}
            items.append({
                "text": chunk,
                "similarity": score,
                "section_id": meta.get("section_id", ""),
                "section_title": meta.get("section_title", ""),
                "parent_title": meta.get("parent_title", ""),
                "page_start": meta.get("page_start", 1),
                "page_end": meta.get("page_end", 1),
            })
            sec_lbl = f" [{meta.get('section_title')}, P.{meta.get('page_start')}]" if meta.get('section_title') else ""
            print(f"  📎 Similarity {score:.3f}{sec_lbl}: {chunk[:70].strip()}…")

        return items

    def retrieve(self, doc_id: str, question: str, top_k: int = TOP_K) -> List[str]:
        """
        Semantically retrieve top-K most relevant chunks (backward-compatible).
        Returns list of text strings.
        """
        items = self.retrieve_with_metadata(doc_id, question, top_k)
        return [item["text"] for item in items]

    def document_indexed(self, doc_id: str) -> bool:
        """Check if a document has already been indexed"""
        try:
            col = self.chroma.get_collection(self._col_name(doc_id))
            return col.count() > 0
        except Exception:
            return False

    def delete_document(self, doc_id: str):
        """Remove a document's index from ChromaDB"""
        try:
            self.chroma.delete_collection(self._col_name(doc_id))
            self._collections.pop(doc_id, None)
            print(f"🗑️  Deleted index for doc: {doc_id}")
        except Exception:
            pass

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _chunk_text(self, text: str) -> List[str]:
        """
        Split text into overlapping chunks.
        Guaranteed to terminate and advance monotonically.
        """
        text = text.strip()
        if not text:
            return []

        # If document fits within one chunk, return directly
        if len(text) <= CHUNK_SIZE:
            return [text]

        chunks = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + CHUNK_SIZE, text_len)
            # Try to break at a sentence/newline boundary for cleaner chunks
            if end < text_len:
                for sep in ['\n\n', '\n', '. ', ' ']:
                    boundary = text.rfind(sep, start + CHUNK_SIZE // 2, end)
                    if boundary != -1:
                        end = boundary + len(sep)
                        break

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            if end >= text_len:
                break

            # Advance start: move by (end - CHUNK_OVERLAP), strictly guaranteeing progress
            next_start = end - CHUNK_OVERLAP
            if next_start <= start:
                next_start = start + max(1, CHUNK_SIZE - CHUNK_OVERLAP)
            start = next_start

        return chunks

    def _col_name(self, doc_id: str) -> str:
        """
        ChromaDB collection name — must satisfy:
        3-63 characters, start and end with an alphanumeric character,
        and only contain [a-zA-Z0-9._-].
        """
        base = "".join(c if c.isalnum() else "_" for c in doc_id).strip("_")
        if not base:
            base = "doc"
        col_prefix = f"doc_{base}"[:45]
        suffix = hashlib.md5(doc_id.encode('utf-8')).hexdigest()[:8]
        clean_name = f"{col_prefix}_{suffix}".strip("_")
        return clean_name

    def _get_or_create_collection(self, doc_id: str):
        if doc_id not in self._collections:
            self._collections[doc_id] = self.chroma.get_or_create_collection(
                name=self._col_name(doc_id),
                metadata={"hnsw:space": "cosine"},  # Cosine similarity
            )
        return self._collections[doc_id]

    def _get_collection(self, doc_id: str):
        try:
            if doc_id not in self._collections:
                self._collections[doc_id] = self.chroma.get_collection(
                    self._col_name(doc_id)
                )
            return self._collections[doc_id]
        except Exception:
            return None

