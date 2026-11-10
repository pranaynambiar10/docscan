from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import sqlite3
import threading
from datetime import datetime
from file_processor import FileProcessor
from AI_service import AIService
from rag_engine import RAGEngine
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Configuration
UPLOAD_FOLDER = 'uploads'
DATABASE = 'documents.db'

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ── Initialize services (singletons — shared across all Gunicorn workers) ─────
file_processor = FileProcessor(UPLOAD_FOLDER)
ai_service     = AIService()
rag_engine     = RAGEngine()          # Local ChromaDB + sentence-transformers

# ── Optimized SQLite: thread-local connections + WAL mode ─────────────────────
_db_local = threading.local()


def get_db():
    """Return a thread-local SQLite connection with WAL mode enabled"""
    if not hasattr(_db_local, 'conn') or _db_local.conn is None:
        _db_local.conn = sqlite3.connect(DATABASE, check_same_thread=False)
        _db_local.conn.execute("PRAGMA journal_mode=WAL")
        _db_local.conn.execute("PRAGMA synchronous=NORMAL")
        _db_local.conn.execute("PRAGMA cache_size=10000")
        _db_local.conn.execute("PRAGMA temp_store=MEMORY")
    return _db_local.conn


def init_database():
    """Initialize SQLite database schema"""
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            filepath TEXT NOT NULL,
            content TEXT,
            chunk_count INTEGER DEFAULT 0,
            upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute('''
        CREATE INDEX IF NOT EXISTS idx_documents_filename
        ON documents (filename, upload_time DESC)
    ''')
    conn.commit()


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/upload', methods=['POST'])
def upload_file():
    """
    Handle file upload, text extraction, and RAG indexing.

    Flow:
      1. Save file
      2. Extract text (PyMuPDF / PaddleOCR / python-docx)
      3. Embed text chunks → store in ChromaDB (RAG index)
      4. Save metadata to SQLite
    """
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        # Step 1 & 2: Extract text
        result = file_processor.process_file(file)

        if not result['success']:
            return jsonify({'error': result['error']}), 400

        filename   = result['filename']
        content    = result['content']
        doc_id     = filename  # Use filename as doc identifier

        # Step 3: Index into RAG (embed chunks → ChromaDB)
        chunk_count = rag_engine.index_document(doc_id, content)

        # Step 4: Persist metadata in SQLite
        conn = get_db()
        conn.execute(
            '''INSERT INTO documents (filename, filepath, content, chunk_count)
               VALUES (?, ?, ?, ?)''',
            (filename, result['filepath'], content, chunk_count)
        )
        conn.commit()

        return jsonify({
            'message': 'File uploaded, processed, and indexed successfully',
            'filename': filename,
            'chunk_count': chunk_count,
            'rag_enabled': chunk_count > 0,
        })

    except Exception as e:
        print(f"Upload error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/chat', methods=['POST'])
def chat():
    """
    Handle chat messages using RAG-powered retrieval.

    Flow:
      1. Embed the user's question
      2. Retrieve top-K semantically relevant chunks from ChromaDB
      3. Send only those chunks to the LLM (not the full document)
      4. Return the answer
    """
    try:
        data = request.get_json()
        print("📨 Incoming chat request:", data)

        message    = data.get('message')
        filename   = data.get('filename')
        model_tier = data.get('model_tier') or data.get('tier', 'auto')

        if not message or not filename:
            return jsonify({'error': 'Message and filename required'}), 400

        doc_id = filename

        # Step 1 & 2: RAG retrieval — semantic search over document chunks
        rag_chunks = []
        if rag_engine.document_indexed(doc_id):
            rag_chunks = rag_engine.retrieve(doc_id, message)
            print(f"📚 RAG: retrieved {len(rag_chunks)} chunks for query: '{message}'")
        else:
            # Fallback: load full text from SQLite and use keyword chunking
            print(f"⚠️  No RAG index for '{doc_id}', falling back to keyword search")
            conn = get_db()
            row = conn.execute(
                'SELECT content FROM documents WHERE filename = ? ORDER BY upload_time DESC LIMIT 1',
                (filename,)
            ).fetchone()
            if not row:
                return jsonify({'error': 'Document not found'}), 404

            # Re-index on-the-fly so next query will use RAG
            content = row[0]
            rag_engine.index_document(doc_id, content)
            rag_chunks = rag_engine.retrieve(doc_id, message)

        # Step 3: Get AI response with retrieved chunks and adaptive model routing
        response, model_used = ai_service.get_response(
            question=message,
            document_content="",   # Not needed — RAG chunks are used
            filename=filename,
            rag_chunks=rag_chunks,
            model_tier=model_tier,
        )

        return jsonify({
            'response': response,
            'chunks_used': len(rag_chunks),
            'rag_enabled': True,
            'model_used': model_used,
            'model_tier': model_tier,
        })

    except Exception as e:
        print(f"Chat error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'rag': 'enabled',
        'deep_model': ai_service.deep_model,
        'fast_model': ai_service.fast_model,
    })


@app.route('/documents', methods=['GET'])
def list_documents():
    """List all indexed documents"""
    conn = get_db()
    rows = conn.execute(
        'SELECT filename, chunk_count, upload_time FROM documents ORDER BY upload_time DESC'
    ).fetchall()
    return jsonify([
        {'filename': r[0], 'chunk_count': r[1], 'upload_time': r[2]}
        for r in rows
    ])


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    init_database()
    print("🚀 DocScan server starting on http://0.0.0.0:5000")
    print("🧠 RAG pipeline: ChromaDB + sentence-transformers ACTIVE")
    print(f"🤖 LLM: {ai_service.model} via Ollama")
    print()
    print("💡 For production, use Gunicorn:")
    print("   gunicorn -w 4 -k gevent --worker-connections 100 -b 0.0.0.0:5000 app:app")
    app.run(debug=False, port=5000, host='0.0.0.0')
