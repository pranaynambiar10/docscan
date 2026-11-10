import requests
import json
import os
import time


class AIService:
    def __init__(self):
        # Configurable via .env — no code change needed to switch models
        self.ollama_url = os.getenv("OLLAMA_URL", "http://ollama:11434/api/generate")
        self.model = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
        self._wait_for_ollama()

    def _wait_for_ollama(self, retries=10, delay=3):
        """Wait for Ollama to be ready (important on Docker startup)"""
        base_url = self.ollama_url.replace("/api/generate", "")
        for attempt in range(retries):
            try:
                r = requests.get(f"{base_url}/api/tags", timeout=5)
                if r.status_code == 200:
                    models = [m['name'] for m in r.json().get('models', [])]
                    print(f"✅ Ollama ready. Available models: {models}")
                    print(f"✅ Using model: {self.model}")
                    return
            except Exception:
                pass
            print(f"⏳ Waiting for Ollama... ({attempt + 1}/{retries})")
            time.sleep(delay)
        print("⚠️  Ollama not reachable at startup — requests will fail until it's up")

    def _query_ollama(self, prompt: str) -> str:
        """Query Ollama with optimized settings for speed"""
        try:
            response = requests.post(
                self.ollama_url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": True,
                    "options": {
                        "num_ctx": 4096,     # Limit context window (faster inference)
                        "num_predict": 512,  # Cap output tokens
                        "temperature": 0.1,  # Low temp = deterministic + faster
                        "top_p": 0.9,
                    }
                },
                stream=True,
                timeout=90,
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
            print(f"Ollama API error: {e}")
            return f"Ollama API error: {e}"

    # ── RAG-powered Q&A ────────────────────────────────────────────────────────

    def get_response(self, question: str, document_content: str,
                     filename: str, rag_chunks: list = None) -> str:
        """
        Answer a question about a document.

        If rag_chunks are provided (from RAG retrieval), only those semantically
        relevant chunks are sent to the LLM — not the full document.
        This gives much better accuracy on large bill/invoice PDFs.
        """
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

        return self._query_ollama(prompt)

    def analyze_document(self, document_content: str, filename: str,
                         rag_chunks: list = None) -> str:
        """Generate a structured summary of a document"""
        # Use first few chunks for summary (most bills have header info at top)
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
        return self._query_ollama(prompt)

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
