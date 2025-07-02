
# DocScan - AI-Powered Document OCR and Q&A (with Ollama)

DocScan is a full-stack application that lets users upload documents (PDFs, images, DOCX), extract text using OCR, and ask questions about the content using a local large language model (LLM) powered by Ollama (LLaMA 3.2).
                                                Developers
                               Pranay Nambiar(CUSAT)    Noor Muhammad KP(CUSAT)
---

Features:
- Upload PDF, image, or Word documents
- Automatically extract text using PyMuPDF, PaddleOCR, and python-docx
- Ask intelligent questions using a local LLM (LLaMA 3.2)
- Store and manage documents using SQLite
- React and Tailwind CSS-based modern UI

---

Tech Stack:
- Frontend: React, TypeScript, Tailwind CSS, Vite
- Backend: Python, Flask, SQLite, OCR (PaddleOCR, PyMuPDF, python-docx)
- LLM: Ollama with LLaMA 3.2

---

Setup Instructions:

1. Clone the repository:

```

git clone <your-repo-url>
cd invoice

```

2. Create and activate a Python virtual environment:

```

python -m venv venv

# On Windows

venv\Scripts\activate

# On macOS/Linux

source venv/bin/activate

```

3. Install backend dependencies:

```

pip install -r requirements.txt

````

4. Set up Ollama and download the LLaMA 3.2 model:

- Install Ollama from https://ollama.com/
- Open a terminal and run:
  ```
  ollama pull llama3.2
  ollama serve
  ```

5. Start the backend:

````

cd backend
python app.py

```

6. Start the frontend:

```

cd ../frontend
npm install
npm run dev

```

Open your browser at `http://localhost:5173`.

---

How to Use:
- Upload a document (invoice, receipt, etc.)
- The app will extract and display the text
- Ask questions like "What is the total amount?" or "Who is the sender?"
- The AI will respond based on the extracted document content

---

Project Structure:

```

invoice/
backend/
app.py
AI\_service.py
file\_processor.py
requirements.txt
uploads/
documents.db
frontend/
src/
public/
package.json
...

```

---

License: MIT
```

---
