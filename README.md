# Invoice Project (docscan)

A full-stack application for intelligent document (invoice, image, docx) upload, OCR, and Q&A using a local LLM.

---

## Features
- Upload PDF, image, or docx files
- Automatic text extraction (PyMuPDF, PaddleOCR, python-docx)
- Store and manage documents in SQLite
- Ask questions about uploaded documents using a local LLM (e.g., llama.cpp, Ollama)
- Modern React/TypeScript frontend with Tailwind CSS

---

## Tech Stack
- **Backend:** Python, Flask, SQLite, PaddleOCR, PyMuPDF, python-docx
- **Frontend:** React, TypeScript, Tailwind CSS, Vite
- **AI:** Local LLM (llama.cpp, Ollama, etc.)

---

## Setup Instructions

### 1. Clone the repository
```bash
git clone <your-repo-url>
cd invoice
```

### 2. Backend Setup
```bash
cd backend
python -m venv venv
venv\Scripts\activate  # On Windows
# or
source venv/bin/activate  # On Mac/Linux
pip install -r requirements.txt
```

- Create a `.env` file for environment variables (if needed).
- The backend will auto-create `uploads/` and `documents.db` if missing.

#### Run the backend:
```bash
python app.py
```

### 3. Frontend Setup
```bash
cd ../frontend
npm install
npm run dev
```

---

## Environment Variables
- Place any required API keys or settings in a `.env` file in the backend directory.
- Example:
  ```
  GEMINI_API_KEY=your_key_here  # Only if using Gemini, otherwise ignore
  ```

---

## Usage
- Visit `http://localhost:5173` (or the port shown) for the frontend.
- Upload a document, view extracted text, and ask questions about its content.

---

## Project Structure
```
invoice/
  backend/
    app.py
    AI_service.py
    file_processor.py
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

## Contribution Guidelines
- Fork the repo and create a feature branch
- Commit descriptive messages
- Open a pull request for review

---

## License
MIT 