import requests
import json
import os
import time


class AIService:
    def __init__(self):
        # Configurable via .env — Dual-model adaptive routing
        self.ollama_url = os.getenv("OLLAMA_URL", "http://ollama:11434/api/generate")
        self.deep_model = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")        # Deep analysis (large docs)
        self.fast_model = os.getenv("OLLAMA_FAST_MODEL", "qwen2.5:1.5b") # High speed (small docs)
        self.model = self.deep_model  # Default compatibility alias
        self._wait_for_ollama()

    def _wait_for_ollama(self):
        """Quick non-blocking check if Ollama is running"""
        base_url = self.ollama_url.replace("/api/generate", "")
        try:
            r = requests.get(f"{base_url}/api/tags", timeout=1)
            if r.status_code == 200:
                models = [m['name'] for m in r.json().get('models', [])]
                print(f"✅ Ollama ready. Available models: {models}")
                print(f"✅ Fast Model: {self.fast_model} | Deep Model: {self.deep_model}")
                return
        except Exception:
            pass
        print("💡 Ollama is not detected locally yet. (Start Ollama when you're ready to query the LLM).")

    def resolve_model(self, model_tier: str = "auto", chunk_count: int = 1) -> str:
        """
        Adaptive Model Routing:
        - Small docs (<= 3 chunks): automatically selects fast 1.5B model (<1s response)
        - Large docs (> 3 chunks): automatically selects 3B deep reasoning model with RAG
        - Explicit override: 'fast' or 'accurate'/'deep'
        """
        tier = (model_tier or "auto").lower()
        if tier == "fast":
            return self.fast_model
        elif tier in ["accurate", "deep"]:
            return self.deep_model
        
        # Auto mode: route based on document size / chunk count
        if chunk_count <= 3:
            print(f"⚡ Small document detected ({chunk_count} chunks) -> Auto-routed to {self.fast_model}")
            return self.fast_model
        else:
            print(f"🎯 Large document detected ({chunk_count} chunks) -> Auto-routed to {self.deep_model}")
            return self.deep_model

    def _query_ollama(self, prompt: str, target_model: str = None) -> str:
        """Query Ollama with model-specific optimized settings"""
        selected_model = target_model or self.deep_model
        is_fast = (selected_model == self.fast_model)

        # Tune context & prediction limits based on model size
        options = {
            "num_ctx": 2048 if is_fast else 4096,
            "num_predict": 256 if is_fast else 512,
            "temperature": 0.1,
            "top_p": 0.9,
        }

        try:
            response = requests.post(
                self.ollama_url,
                json={
                    "model": selected_model,
                    "prompt": prompt,
                    "stream": True,
                    "options": options,
                },
                stream=True,
                timeout=60 if is_fast else 90,
            )
            response.raise_for_status()
            result = ""
            for line in response.iter_lines():
                if line:
                    data = json.loads(line.decode("utf-8"))
                    result += data.get("response", "")
            return result if result else "No response from Ollama."
        except requests.exceptions.Timeout:
            return "The AI took too long to respond. Please try again."
        except Exception as e:
            return f"Ollama connection error ({selected_model}): {e}. Make sure Ollama is running (`ollama serve`)."

    # ── RAG-powered Q&A ────────────────────────────────────────────────────────

    def get_response(self, question: str, document_content: str,
                     filename: str, rag_chunks: list = None,
                     model_tier: str = "auto") -> tuple:
        """
        Answer a question about a document.
        Returns: (answer_string, model_used_name)
        """
        chunk_count = len(rag_chunks) if rag_chunks else (1 if document_content else 0)
        target_model = self.resolve_model(model_tier, chunk_count)

        if rag_chunks:
            # ── RAG mode: use semantically retrieved chunks ──────────────────
            context = "\n\n---\n\n".join(rag_chunks)
            prompt = f"""You are an expert document analyst specializing in bills, invoices, and financial documents.

Document: {filename}

Relevant Sections (retrieved by semantic search):
{context}

User Question: {question}

Instructions:
- Answer based ONLY on the retrieved sections above.
- For amounts/totals: quote the exact figure from the document.
- If the answer is not in the retrieved sections, say: "This information was not found in the retrieved sections. Try rephrasing your question."
- Be concise and precise.

Answer:"""
        else:
            # ── Fallback mode: keyword-matched chunk (no RAG index yet) ─────
            chunks = self.chunk_document(document_content)
            relevant_chunk = self.find_relevant_chunk(chunks, question)
            prompt = f"""You are a document analyst. Answer based on the document excerpt below.

Document: {filename}
Excerpt:
{relevant_chunk}

Question: {question}

Answer concisely. If not in the excerpt, say so.

Answer:"""

        answer = self._query_ollama(prompt, target_model=target_model)
        return answer, target_model

    def analyze_document(self, document_content: str, filename: str,
                         rag_chunks: list = None, model_tier: str = "auto") -> tuple:
        """Generate a structured summary of a document"""
        chunk_count = len(rag_chunks) if rag_chunks else 1
        target_model = self.resolve_model(model_tier, chunk_count)

        if rag_chunks:
            context = "\n\n".join(rag_chunks[:3])
        else:
            context = document_content[:2000]

        prompt = f"""Analyze this document and provide a structured summary:

Document: {filename}
Content:
{context}

Provide:
1. Document type (invoice / bill / receipt / other)
2. Key parties (vendor, customer, etc.)
3. Key amounts or totals
4. Important dates
5. Any action items or due dates

Summary:"""
        summary = self._query_ollama(prompt, target_model=target_model)
        return summary, target_model

    # ── Fallback chunking (used when RAG index is not available) ──────────────

    def chunk_document(self, text: str, chunk_size: int = 2000,
                       overlap: int = 200) -> list:
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunks.append(text[start:end])
            start += chunk_size - overlap
        return chunks

    def find_relevant_chunk(self, chunks: list, question: str) -> str:
        question_words = set(question.lower().split())
        best_chunk = chunks[0]
        max_matches = 0
        for chunk in chunks:
            chunk_words = set(chunk.lower().split())
            matches = len(question_words & chunk_words)
            if matches > max_matches:
                max_matches = matches
                best_chunk = chunk
        return best_chunk

    def extract_invoice_data(self, file_path, mime_type):
        return "Image/PDF extraction is not supported with local LLMs. Please use OCR to extract text first."
