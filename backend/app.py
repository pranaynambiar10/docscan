import os
# Prevent Intel OpenMP deadlock when PyTorch and PaddleOCR co-exist on Windows
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
try:
    import torch
    torch.set_num_threads(2)
except ImportError:
    pass

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import re
import sqlite3
import threading
from datetime import datetime
from file_processor import FileProcessor
from AI_service import AIService
from rag_engine import RAGEngine
from section_manager import SectionManager
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
print("⏳ Initializing DocScan backend services...")
file_processor  = FileProcessor(UPLOAD_FOLDER)
ai_service      = AIService()
rag_engine      = RAGEngine()          # Local ChromaDB + sentence-transformers
section_manager = SectionManager(DATABASE) # Section-aware parser and retrieval
print("✅ All backend services ready!")

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
    """Initialize SQLite database schema and migrate missing columns"""
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
    # Auto-migrate chunk_count column if older database exists
    cursor = conn.execute("PRAGMA table_info(documents)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'chunk_count' not in columns:
        conn.execute("ALTER TABLE documents ADD COLUMN chunk_count INTEGER DEFAULT 0")
    conn.commit()

# Always initialize database schema on startup
init_database()


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
            print("❌ [UPLOAD] Rejected: 'file' field missing from request.files")
            return jsonify({'error': "No file provided in form data ('file' key missing)"}), 400

        file = request.files['file']
        if not file or file.filename == '':
            print("❌ [UPLOAD] Rejected: Empty filename")
            return jsonify({'error': 'No file selected for upload'}), 400

        filename = file.filename
        print(f"\n📥 [UPLOAD] Incoming upload request for file: '{filename}'")

        # Step 1: Text extraction
        print(f"⚙️ [UPLOAD] Step 1/4: Extracting text from '{filename}'...")
        result = file_processor.process_file(file)

        if not result['success']:
            err_msg = result.get('error', 'Failed to extract text from document')
            print(f"❌ [UPLOAD] Extraction failed: {err_msg}")
            return jsonify({'error': err_msg}), 400

        content = result['content']
        doc_id  = filename
        print(f"📄 [UPLOAD] Step 1 complete. Extracted {len(content)} characters.")

        # Step 2: Parse and preserve structured sections & module boundaries
        print(f"📑 [UPLOAD] Step 2/4: Parsing document sections and module boundaries...")
        sections = section_manager.parse_document_sections(result['filepath'], filename)
        section_manager.save_sections(filename, sections)
        print(f"✅ [UPLOAD] Step 2 complete. Discovered {len(sections)} structured section(s).")

        # Step 3: Index into ChromaDB (Section-aware RAG)
        print(f"🧠 [UPLOAD] Step 3/4: Chunking and indexing into ChromaDB (RAG)...")
        chunk_count = rag_engine.index_document(doc_id, content, sections=sections)
        print(f"✅ [UPLOAD] Step 3 complete. Indexed {chunk_count} chunk(s).")

        # Step 4: Persist metadata in SQLite
        print(f"💾 [UPLOAD] Step 4/4: Saving document metadata to SQLite...")
        conn = get_db()
        conn.execute(
            '''INSERT INTO documents (filename, filepath, content, chunk_count)
               VALUES (?, ?, ?, ?)''',
            (filename, result['filepath'], content, chunk_count)
        )
        conn.commit()
        print(f"🎉 [UPLOAD] Successfully processed, structured, and indexed '{filename}'!\n")

        return jsonify({
            'message': f"Document '{filename}' uploaded, structured, and indexed successfully.",
            'filename': filename,
            'chunk_count': chunk_count,
            'section_count': len(sections),
            'rag_enabled': chunk_count > 0,
            'characters_extracted': len(content)
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"❌ [UPLOAD] Exception during upload: {str(e)}")
        return jsonify({'error': f"Internal server error: {str(e)}"}), 500


@app.route('/chat', methods=['POST'])
def chat():
    """
    Handle chat messages with Dual-Mode Intelligence:
      Mode A: Semantic RAG retrieval for focused queries
      Mode B: Full Section / Complete Syllabus retrieval for comprehensive requests
    """
    try:
        data = request.get_json()
        print("📨 Incoming chat request:", data)

        message      = data.get('message')
        filename     = data.get('filename')
        model_tier   = data.get('model_tier') or data.get('tier', 'auto')
        context_hint = data.get('context_hint', '')

        if not message or not filename:
            return jsonify({'error': 'Message and filename required'}), 400

        doc_id = filename

        # ── Step 1: Intelligent Query Classifier (Full Section Resolution) ────
        # Checks if user asked for complete module, full syllabus, or entire section
        section_res = section_manager.resolve_query_section(filename, message, context_hint=context_hint)

        if section_res.get('is_full_request'):
            print(f"📜 [CHAT] Mode B Triggered: Full Section Retrieval ({section_res['mode']}) -> '{section_res['section_title']}' ({section_res.get('page_range')})")
            response, model_used = ai_service.get_response(
                question=message,
                document_content=section_res['full_text'],
                filename=filename,
                rag_chunks=None,
                model_tier='full',
            )

            return jsonify({
                'response': response,
                'retrieval_mode': section_res['mode'],
                'chunks_used': 0,
                'rag_enabled': False,
                'full_section_used': True,
                'model_used': model_used,
                'model_tier': model_tier,
                'matched_section': {
                    'section_id': section_res.get('matched_section_id', ''),
                    'section_title': section_res['section_title'],
                    'parent_title': section_res.get('parent_title', ''),
                    'page_range': section_res.get('page_range', ''),
                    'full_text': section_res['full_text']
                },
                'sources': []
            })

        # ── Step 2: Explicit Full Document Mode (user clicked '📜 Full Doc') ───
        if model_tier in ['full', 'fulldoc']:
            print(f"📜 [CHAT] Explicit Full Document Mode for: '{filename}'")
            conn = get_db()
            row = conn.execute(
                'SELECT content FROM documents WHERE filename = ? ORDER BY upload_time DESC LIMIT 1',
                (filename,)
            ).fetchone()
            if not row:
                return jsonify({'error': f"Document '{filename}' not found"}), 404

            full_content = row[0] or ""
            response, model_used = ai_service.get_response(
                question=message,
                document_content=full_content,
                filename=filename,
                rag_chunks=None,
                model_tier='full',
            )

            return jsonify({
                'response': response,
                'retrieval_mode': 'full_document',
                'chunks_used': 0,
                'rag_enabled': False,
                'full_doc_used': True,
                'model_used': model_used,
                'model_tier': 'full',
                'sources': [],
            })

        # ── Step 3: Mode A: Semantic RAG retrieval over document chunks ───────
        rag_items = []
        if rag_engine.document_indexed(doc_id):
            rag_items = rag_engine.retrieve_with_metadata(doc_id, message, top_k=5)
            print(f"📚 RAG: retrieved {len(rag_items)} chunks for query: '{message}'")
        else:
            conn = get_db()
            row = conn.execute(
                'SELECT content FROM documents WHERE filename = ? ORDER BY upload_time DESC LIMIT 1',
                (filename,)
            ).fetchone()
            if not row:
                return jsonify({'error': 'Document not found'}), 404

            content = row[0]
            sections = section_manager.parse_document_sections(os.path.join(UPLOAD_FOLDER, filename), filename)
            section_manager.save_sections(filename, sections)
            rag_engine.index_document(doc_id, content, sections=sections)
            rag_items = rag_engine.retrieve_with_metadata(doc_id, message, top_k=5)

        rag_chunks = [item['text'] for item in rag_items]

        # Determine best matching section from retrieved chunks by scoring title & parent relevance
        matched_section_info = None
        if rag_items:
            best_sec = None
            best_score = -1
            query_context = f"{message} {context_hint}".lower()
            query_words = [w for w in re.split(r'[^a-zA-Z0-9]+', query_context) if len(w) > 3]

            for item in rag_items:
                sec = None
                sec_id = item.get('section_id')
                if sec_id:
                    sec = section_manager.get_section_by_id(filename, sec_id)
                if not sec and item.get('text'):
                    sec = section_manager.find_section_for_chunk(filename, item['text'])

                if sec:
                    # Score by word overlap with query & context hint
                    sec_title = f"{sec['section_title']} {sec.get('parent_title', '')}".lower()
                    score = sum(3 for w in query_words if w in sec_title)
                    if score > best_score:
                        best_score = score
                        best_sec = sec

            if not best_sec and rag_items:
                # Fallback to first chunk's section
                if rag_items[0].get('section_id'):
                    best_sec = section_manager.get_section_by_id(filename, rag_items[0]['section_id'])
                elif rag_items[0].get('text'):
                    best_sec = section_manager.find_section_for_chunk(filename, rag_items[0]['text'])

            if best_sec:
                matched_section_info = {
                    'section_id': best_sec['section_id'],
                    'section_title': best_sec['section_title'],
                    'parent_title': best_sec.get('parent_title', ''),
                    'page_range': f"Page {best_sec['page_start']}" if best_sec['page_start'] == best_sec['page_end'] else f"Pages {best_sec['page_start']}–{best_sec['page_end']}",
                    'full_text': best_sec['content']
                }

        # Query LLM with RAG chunks
        response, model_used = ai_service.get_response(
            question=message,
            document_content="",
            filename=filename,
            rag_chunks=rag_chunks,
            model_tier=model_tier,
        )

        return jsonify({
            'response': response,
            'retrieval_mode': 'rag',
            'chunks_used': len(rag_chunks),
            'rag_enabled': True,
            'full_doc_used': False,
            'model_used': model_used,
            'model_tier': model_tier,
            'matched_section': matched_section_info,
            'sources': rag_chunks,
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
    """List all indexed documents (deduplicated by filename)"""
    conn = get_db()
    rows = conn.execute('''
        SELECT filename, MAX(chunk_count) as max_chunks, MAX(upload_time) as latest_time
        FROM documents
        GROUP BY filename
        ORDER BY latest_time DESC
    ''').fetchall()
    return jsonify([
        {'filename': r[0], 'chunk_count': r[1], 'upload_time': r[2]}
        for r in rows
    ])


@app.route('/documents/<path:filename>', methods=['DELETE'])
def delete_document(filename):
    """Delete a document from SQLite and ChromaDB"""
    try:
        conn = get_db()
        conn.execute('DELETE FROM documents WHERE filename = ?', (filename,))
        conn.execute('DELETE FROM document_sections WHERE document_id = ?', (filename,))
        conn.commit()

        # Delete from ChromaDB vector collection
        rag_engine.delete_document(filename)

        # Optionally remove physical file
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception:
                pass

        print(f"🗑️ Deleted document '{filename}' from database and vector index")
        return jsonify({'message': f"Document '{filename}' deleted successfully"}), 200
    except Exception as e:
        print(f"❌ Delete error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/documents/<path:filename>/content', methods=['GET'])
def get_document_content(filename):
    """Fetch full extracted text and metadata for a document"""
    try:
        conn = get_db()
        row = conn.execute(
            'SELECT content, chunk_count, upload_time FROM documents WHERE filename = ? ORDER BY upload_time DESC LIMIT 1',
            (filename,)
        ).fetchone()
        if not row:
            return jsonify({'error': f"Document '{filename}' not found"}), 404

        content = row[0] or ''
        return jsonify({
            'filename': filename,
            'content': content,
            'chunk_count': row[1] or 0,
            'upload_time': row[2],
            'character_count': len(content)
        }), 200
    except Exception as e:
        print(f"❌ Get content error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/documents/<path:filename>/sections', methods=['GET'])
def get_document_sections(filename):
    """Fetch structured sections and page ranges for a document"""
    try:
        sections = section_manager.get_sections(filename)
        return jsonify({
            'filename': filename,
            'total_sections': len(sections),
            'sections': sections
        }), 200
    except Exception as e:
        print(f"❌ Get sections error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/documents/<path:filename>/sections/<path:section_id>', methods=['GET'])
def get_document_section_by_id(filename, section_id):
    """Fetch complete un-truncated content of a specific section"""
    try:
        section = section_manager.get_section_by_id(filename, section_id)
        if not section:
            return jsonify({'error': f"Section '{section_id}' not found for document '{filename}'"}), 404
        return jsonify(section), 200
    except Exception as e:
        print(f"❌ Get section by id error: {e}")
        return jsonify({'error': str(e)}), 500


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
