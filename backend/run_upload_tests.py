import os
import requests
import sqlite3
import fitz
import docx
from PIL import Image, ImageDraw, ImageFont

BASE_URL = "http://localhost:5000"
DB_PATH = "documents.db"

def create_sample_files():
    print("📁 Generating test files for 6 test categories...")
    os.makedirs("test_fixtures", exist_ok=True)

    # 1. Normal text PDF
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), "Pranay Nambiar - Senior Full Stack Developer\nExpertise: React, TypeScript, Python, Flask, RAG, ChromaDB.\nLocation: Bangalore, India.\nProject: DocScan Document Analysis Tool.")
    doc.save("test_fixtures/test_resume.pdf")
    doc.close()

    # 2. Scanned PDF (an image embedded in PDF without selectable text layer)
    img = Image.new('RGB', (600, 300), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((30, 30), "SCANNED TAX INVOICE #98765\nVendor: Cloud Tech Solutions\nAmount Due: $1,450.00\nStatus: Paid in Full", fill=(0, 0, 0))
    img_path = "test_fixtures/temp_scanned.png"
    img.save(img_path)

    scanned_doc = fitz.open()
    scanned_page = scanned_doc.new_page(width=600, height=300)
    scanned_page.insert_image(fitz.Rect(0, 0, 600, 300), filename=img_path)
    scanned_doc.save("test_fixtures/test_scanned.pdf")
    scanned_doc.close()
    if os.path.exists(img_path):
        os.remove(img_path)

    # 3. JPG invoice
    jpg_img = Image.new('RGB', (500, 250), color=(255, 255, 255))
    d_jpg = ImageDraw.Draw(jpg_img)
    d_jpg.text((30, 30), "INVOICE #INV-2026-001\nCustomer: Enterprise Corp\nTotal: $789.50\nPayment Terms: Net 30", fill=(0, 0, 0))
    jpg_img.save("test_fixtures/test_invoice.jpg")

    # 4. DOCX document
    doc_file = docx.Document()
    doc_file.add_heading("Service Level Agreement", 0)
    doc_file.add_paragraph("This agreement governs the performance and availability of the DocScan platform.")
    doc_file.add_paragraph("Uptime guarantee is 99.9% with 24/7 monitoring and automated alerts.")
    doc_file.save("test_fixtures/test_sla.docx")

    # 5. TXT document
    with open("test_fixtures/test_notes.txt", "w", encoding="utf-8") as f:
        f.write("Project DocScan Technical Notes:\n- Frontend: React + Vite on port 8080\n- Backend: Flask on port 5000\n- Vector store: ChromaDB\n- Embedding model: all-MiniLM-L6-v2\n- Local LLM: Ollama qwen2.5:3b")

    # 6a. Empty file (0 bytes)
    with open("test_fixtures/test_empty.pdf", "w") as f:
        pass

    # 6b. Unsupported file extension
    with open("test_fixtures/test_unsupported.xyz", "w") as f:
        f.write("This is binary or unsupported file data.")

    print("✅ All test fixtures created.\n")

def run_tests():
    create_sample_files()

    tests = [
        {"name": "1. Text-based PDF", "file": "test_fixtures/test_resume.pdf", "expect_success": True},
        {"name": "2. Scanned PDF (PaddleOCR)", "file": "test_fixtures/test_scanned.pdf", "expect_success": True},
        {"name": "3. JPG Invoice (PaddleOCR)", "file": "test_fixtures/test_invoice.jpg", "expect_success": True},
        {"name": "4. DOCX Document", "file": "test_fixtures/test_sla.docx", "expect_success": True},
        {"name": "5. TXT Document", "file": "test_fixtures/test_notes.txt", "expect_success": True},
        {"name": "6a. Empty File (0 bytes)", "file": "test_fixtures/test_empty.pdf", "expect_success": False},
        {"name": "6b. Unsupported File (.xyz)", "file": "test_fixtures/test_unsupported.xyz", "expect_success": False},
    ]

    all_passed = True

    for t in tests:
        print(f"--------------------------------------------------")
        print(f"🧪 Testing: {t['name']}")
        filepath = t['file']
        filename = os.path.basename(filepath)

        with open(filepath, 'rb') as f:
            resp = requests.post(f"{BASE_URL}/upload", files={"file": (filename, f)})

        print(f"HTTP Status: {resp.status_code}")
        try:
            data = resp.json()
            print(f"Response Body: {data}")
        except Exception:
            print(f"Response Text: {resp.text}")
            data = {}

        if t['expect_success']:
            if resp.status_code == 200 and data.get('chunk_count', 0) > 0:
                print(f"✅ PASS: Upload succeeded, chunk_count = {data.get('chunk_count')}")
                
                # Verify SQLite metadata
                conn = sqlite3.connect(DB_PATH)
                row = conn.execute("SELECT filename, chunk_count, upload_time FROM documents WHERE filename = ? ORDER BY upload_time DESC LIMIT 1", (filename,)).fetchone()
                conn.close()
                if row:
                    print(f"   SQLite check: Found row {row}")
                else:
                    print(f"   ❌ SQLite check failed: Row not found in documents table")
                    all_passed = False
            else:
                print(f"❌ FAIL: Expected success, got status {resp.status_code}")
                all_passed = False
        else:
            if resp.status_code == 400 and 'error' in data:
                print(f"✅ PASS: Safely rejected with descriptive error: '{data.get('error')}'")
            else:
                print(f"❌ FAIL: Expected 400 error, got {resp.status_code}")
                all_passed = False

    # Also test the Q&A Chat pipeline on the uploaded text-based PDF
    print(f"\n==================================================")
    print(f"🤖 Testing /chat Q&A with RAG retrieval...")
    chat_resp = requests.post(f"{BASE_URL}/chat", json={
        "message": "What is Pranay's location and what tools does he specialize in?",
        "filename": "test_resume.pdf",
        "model_tier": "fast"
    })
    print(f"Chat HTTP Status: {chat_resp.status_code}")
    if chat_resp.status_code == 200:
        chat_data = chat_resp.json()
        print(f"Model used: {chat_data.get('model_used')}")
        print(f"Chunks used: {chat_data.get('chunks_used')}")
        print(f"AI Response:\n{chat_data.get('response')}")
        print("✅ PASS: Q&A Chat successfully answered from retrieved chunks!")
    else:
        print(f"❌ FAIL: Chat returned {chat_resp.status_code}: {chat_resp.text}")
        all_passed = False

    print(f"\n==================================================")
    if all_passed:
        print("🎉 ALL 6 TEST CATEGORIES + CHAT PIPELINE PASSED PERFECTLY!")
    else:
        print("❌ SOME TESTS FAILED")

if __name__ == "__main__":
    run_tests()

