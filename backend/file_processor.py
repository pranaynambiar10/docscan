# Pre-load PyTorch before PaddleOCR to prevent Windows C++ DLL conflicts
try:
    import torch
except ImportError:
    pass

import os
import hashlib
import docx
from PIL import Image
from paddleocr import PaddleOCR
from concurrent.futures import ThreadPoolExecutor

# PyMuPDF is 5-10x faster than PyPDF2 for PDF extraction (C-backed)
try:
    import pymupdf as fitz  # preferred import (fitz alias is deprecated)
    PYMUPDF_AVAILABLE = True
except ImportError:
    try:
        import fitz  # older pymupdf versions
        PYMUPDF_AVAILABLE = True
    except ImportError:
        PYMUPDF_AVAILABLE = False
        print("⚠️  PyMuPDF not found, falling back to PyPDF2. Install with: pip install pymupdf")

# PaddleOCR GPU detection
try:
    import paddle
    _USE_GPU = paddle.device.is_compiled_with_cuda()
except Exception:
    _USE_GPU = False


class FileProcessor:
    def __init__(self, upload_folder):
        self.upload_folder = upload_folder
        try:
            self.ocr = PaddleOCR(lang='en')
        except Exception as e:
            print(f"⚠️ PaddleOCR default init fallback: {e}")
            self.ocr = PaddleOCR()
        print("✅ PaddleOCR initialized")
        print(f"✅ PDF backend: {'PyMuPDF (fast)' if PYMUPDF_AVAILABLE else 'PyPDF2 (fallback)'}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_file(self, file):
        """Process uploaded file and extract text content"""
        try:
            filename = file.filename
            filepath = os.path.join(self.upload_folder, filename)

            file.save(filepath)

            # --- Deduplication: check hash before heavy OCR/extraction ---
            file_hash = self._get_file_hash(filepath)
            cached = self._check_hash_cache(file_hash)
            if cached:
                print(f"⚡ Cache hit for {filename} — skipping re-processing")
                return {
                    'success': True,
                    'filename': filename,
                    'filepath': filepath,
                    'content': cached,
                }

            content = ""
            file_extension = filename.lower().split('.')[-1]

            if file_extension == 'pdf':
                content = self._extract_pdf_text(filepath)
            elif file_extension == 'txt':
                content = self._extract_txt_text(filepath)
            elif file_extension in ['doc', 'docx']:
                content = self._extract_docx_text(filepath)
            elif file_extension in ['jpg', 'jpeg', 'png']:
                content = self._extract_image_text(filepath)
            else:
                return {
                    'success': False,
                    'error': f'Unsupported file type: {file_extension}'
                }

            if not content.strip():
                return {
                    'success': False,
                    'error': 'Could not extract text from the file'
                }

            # Save hash → content mapping for future duplicate uploads
            self._save_hash_cache(file_hash, content)

            return {
                'success': True,
                'filename': filename,
                'filepath': filepath,
                'content': content
            }

        except Exception as e:
            return {
                'success': False,
                'error': f'Error processing file: {str(e)}'
            }

    # ------------------------------------------------------------------
    # Extraction methods
    # ------------------------------------------------------------------

    def _extract_pdf_text(self, filepath):
        """Extract text from PDF — PyMuPDF is 5-10x faster than PyPDF2"""
        if PYMUPDF_AVAILABLE:
            return self._extract_pdf_pymupdf(filepath)
        return self._extract_pdf_pypdf2(filepath)

    def _extract_pdf_pymupdf(self, filepath):
        """Fast C-backed PDF extraction with parallel page processing"""
        text = ""
        try:
            doc = fitz.open(filepath)
            num_pages = len(doc)

            if num_pages <= 4:
                # Small docs: sequential is fine
                pages_text = [doc[i].get_text() for i in range(num_pages)]
            else:
                # Large docs: parallel page extraction (2-4x speedup)
                def extract_page(page_num):
                    return doc[page_num].get_text()

                with ThreadPoolExecutor(max_workers=min(4, num_pages)) as executor:
                    pages_text = list(executor.map(extract_page, range(num_pages)))

            doc.close()
            text = "\n".join(pages_text)
        except Exception as e:
            print(f"PyMuPDF extraction error: {e}")
        return text

    def _extract_pdf_pypdf2(self, filepath):
        """Fallback PDF extraction using PyPDF2"""
        import PyPDF2
        text = ""
        try:
            with open(filepath, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
        except Exception as e:
            print(f"PDF extraction error: {e}")
        return text

    def _extract_txt_text(self, filepath):
        """Extract text from TXT file"""
        try:
            with open(filepath, 'r', encoding='utf-8') as file:
                return file.read()
        except UnicodeDecodeError:
            with open(filepath, 'r', encoding='latin-1') as file:
                return file.read()

    def _extract_docx_text(self, filepath):
        """Extract text from DOCX file"""
        text = ""
        try:
            doc = docx.Document(filepath)
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
        except Exception as e:
            print(f"DOCX extraction error: {e}")
        return text

    def _extract_image_text(self, filepath):
        """Extract text from image using PaddleOCR (GPU-accelerated if available)"""
        try:
            print(f"Processing image: {filepath}")
            result = self.ocr.ocr(filepath)
            text = ""
            if isinstance(result, list) and len(result) > 0 and isinstance(result[0], dict):
                rec_texts = result[0].get('rec_texts', [])
                text = "\n".join([t for t in rec_texts if t.strip()])
            else:
                for line in result:
                    for word_info in line:
                        if len(word_info) > 1 and isinstance(word_info[1], (list, tuple)):
                            text_piece = word_info[1][0]
                            if isinstance(text_piece, str):
                                text += text_piece + "\n"
            print(f"Extracted {len(text)} chars from image")
            return text
        except Exception as e:
            print(f"PaddleOCR extraction error: {e}")
            return f"Error extracting text from image: {e}"

    # ------------------------------------------------------------------
    # Hash-based deduplication cache (simple file-based)
    # ------------------------------------------------------------------

    def _get_file_hash(self, filepath):
        """Compute MD5 hash of file for deduplication"""
        h = hashlib.md5()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        return h.hexdigest()

    def _cache_path(self, file_hash):
        return os.path.join(self.upload_folder, f".cache_{file_hash}.txt")

    def _check_hash_cache(self, file_hash):
        """Return cached extracted text if this file was seen before"""
        path = self._cache_path(file_hash)
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        return None

    def _save_hash_cache(self, file_hash, content):
        """Cache extracted text keyed by file hash"""
        path = self._cache_path(file_hash)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
