from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import sqlite3
from datetime import datetime
import google.generativeai as genai
from file_processor import FileProcessor
from gemini_service import GeminiService
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

# Initialize services
file_processor = FileProcessor(UPLOAD_FOLDER)
gemini_service = GeminiService()

def init_database():
    """Initialize SQLite database"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            filepath TEXT NOT NULL,
            content TEXT,
            upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload and processing"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Process the file
        result = file_processor.process_file(file)
        
        if result['success']:
            # Store in database
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO documents (filename, filepath, content)
                VALUES (?, ?, ?)
            ''', (result['filename'], result['filepath'], result['content']))
            
            conn.commit()
            conn.close()
            
            return jsonify({
                'message': 'File uploaded and processed successfully',
                'filename': result['filename']
            })
        else:
            return jsonify({'error': result['error']}), 400
            
    except Exception as e:
        print(f"Upload error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/chat', methods=['POST'])
def chat():
    """Handle chat messages"""
    try:
        data = request.get_json()
        print("📨 Incoming chat request:", data)

        message = data.get('message')
        filename = data.get('filename')

        if not message or not filename:
            return jsonify({'error': 'Message and filename required'}), 400

        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT content FROM documents 
            WHERE filename = ? 
            ORDER BY upload_time DESC 
            LIMIT 1
        ''', (filename,))

        result = cursor.fetchone()
        conn.close()

        if not result:
            return jsonify({'error': 'Document not found'}), 404

        document_content = result[0]

        # Get AI response
        response = gemini_service.get_response(message, document_content, filename)

        return jsonify({'response': response})

    except Exception as e:
        print(f"Chat error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    # Get Gemini API key from environment variable
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    
    if not GEMINI_API_KEY:
        print("⚠️  Please set your Gemini API key in the .env file")
        print("   Get your API key from: https://makersuite.google.com/app/apikey")
        print("   Create a .env file with: GEMINI_API_KEY=your_api_key_here")
    else:
        genai.configure(api_key=GEMINI_API_KEY)
    
    init_database()
    print("🚀 Server starting on http://localhost:5000")
    app.run(debug=True, port=5000)
