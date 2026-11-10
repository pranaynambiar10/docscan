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
import hashlib
from typing import List, Tuple

# ChromaDB — local persistent vector store (no server needed)
import chromadb
from chromadb.config import Settings

# Sentence-Transformers — local embedding model (no API key, no internet needed)
from sentence_transformers import SentenceTransformer

# ── Configuration ──────────────────────────────────────────────────────────────
EMBED_MODEL_NAME = os.getenv(
    "EMBED_MODEL",
    "all-MiniLM-L6-v2"       # 22 MB, fast on CPU, great for English docs
    # Alternatives:
    # "all-mpnet-base-v2"    # 420 MB, higher accuracy, slower
    # "paraphrase-MiniLM-L3-v2"  # 17 MB, fastest, slightly lower accuracy
)
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_db")
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
        self.embedder = SentenceTransformer(EMBED_MODEL_NAME)
        dim = self.embedder.get_embedding_dimension()   # renamed from get_sentence_embedding_dimension
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

    def index_document(self, doc_id: str, text: str) -> int:
        """
        Chunk a document, embed each chunk, and store in ChromaDB.
        Returns the number of chunks indexed.
        Call this once after text extraction during upload.
        """
        chunks = self._chunk_text(text)
        if not chunks:
            return 0

        collection = self._get_or_create_collection(doc_id)

        # Embed all chunks in one batched call (much faster than one-by-one)
        embeddings = self.embedder.encode(
            chunks,
            batch_size=32,
            show_progress_bar=False,
            normalize_embeddings=True,   # Cosine similarity via dot product
        ).tolist()

        # Upsert into ChromaDB (safe to re-index same doc)
        ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
        collection.upsert(
            ids=ids,
            documents=chunks,
            embeddings=embeddings,
            metadatas=[{"doc_id": doc_id, "chunk_index": i} for i in range(len(chunks))],
        )

        print(f"✅ Indexed {len(chunks)} chunks for doc: {doc_id}")
        return len(chunks)

    def retrieve(self, doc_id: str, question: str, top_k: int = TOP_K) -> List[str]:
        """
        Semantically retrieve the top-K most relevant chunks for a question.
        Returns a list of text chunks, ranked by relevance.
        """
        collection = self._get_collection(doc_id)
        if collection is None:
            return []

        query_embedding = self.embedder.encode(
            [question],
            normalize_embeddings=True,
        ).tolist()

        results = collection.query(
            query_embeddings=query_embedding,
            n_results=min(top_k, collection.count()),
            include=["documents", "distances"],
        )

        chunks = results["documents"][0] if results["documents"] else []
        distances = results["distances"][0] if results["distances"] else []

        # Log similarity scores for debugging
        for chunk, dist in zip(chunks, distances):
            score = 1 - dist  # Convert distance → similarity
            print(f"  📎 Similarity {score:.3f}: {chunk[:80].strip()}…")

        return chunks

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
        Overlap ensures context isn't lost at chunk boundaries
        (important for bill totals that span across lines).
        """
        chunks = []
        start = 0
        text = text.strip()
        while start < len(text):
            end = min(start + CHUNK_SIZE, len(text))
            # Try to break at a sentence/newline boundary for cleaner chunks
            if end < len(text):
                for sep in ['\n\n', '\n', '. ', ' ']:
                    boundary = text.rfind(sep, start + CHUNK_SIZE // 2, end)
                    if boundary != -1:
                        end = boundary + len(sep)
                        break
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            start = end - CHUNK_OVERLAP
            if start >= len(text):
                break
        return chunks

    def _col_name(self, doc_id: str) -> str:
        """ChromaDB collection name — sanitize to alphanumeric + underscores"""
        safe = "".join(c if c.isalnum() else "_" for c in doc_id)
        # ChromaDB requires 3-63 chars; hash long names
        if len(safe) > 60:
            safe = "doc_" + hashlib.md5(doc_id.encode()).hexdigest()[:56]
        return safe or "default_collection"

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

