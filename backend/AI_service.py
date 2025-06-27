import requests
import json

class AIService:
    def __init__(self):
        self.ollama_url = "http://localhost:11434/api/generate"
        self.model = "llama3.2:latest"

    def _query_ollama(self, prompt):
        try:
            response = requests.post(
                self.ollama_url,
                json={"model": self.model, "prompt": prompt},
                stream=True
            )
            response.raise_for_status()
            result = ""
            for line in response.iter_lines():
                if line:
                    data = json.loads(line.decode("utf-8"))
                    result += data.get("response", "")
            return result if result else "No response from Ollama."
        except Exception as e:
            print(f"Ollama API error: {e}")
            return f"Ollama API error: {e}"

    def extract_invoice_data(self, file_path, mime_type):
        return "Image/PDF extraction is not supported with local LLMs. Please use OCR to extract text first."

    def chunk_document(self, text, chunk_size=2000, overlap=200):
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunks.append(text[start:end])
            start += chunk_size - overlap
        return chunks

    def find_relevant_chunk(self, chunks, question):
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

    def get_response(self, question, document_content, filename):
        prompt = f"""
You are an AI assistant helping users understand documents. 

Document Name: {filename}
Content: {document_content[:600000]}...

User Question: {question}

Please answer the user's question based on the document content provided. Be helpful, accurate, and concise. If the question cannot be answered from the document content, please say so clearly.

Answer:
"""
        return self._query_ollama(prompt)

    def analyze_document(self, document_content, filename):
        prompt = f"""
Please analyze this document and provide a brief summary:

Document Name: {filename}
Content: {document_content[:600000]}...

Please provide:
1. What type of document this appears to be
2. A brief summary of the main content
3. Key information or data points mentioned

Summary:
"""
        return self._query_ollama(prompt) 