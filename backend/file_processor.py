import os
import PyPDF2
import docx
from PIL import Image
import io
from paddleocr import PaddleOCR

class FileProcessor:
    def __init__(self, upload_folder):
        self.upload_folder = upload_folder
        self.ocr = PaddleOCR(lang='en')  
    
    def process_file(self, file):
        """Process uploaded file and extract text content"""
        try:
            filename = file.filename
            filepath = os.path.join(self.upload_folder, filename)
            
            file.save(filepath)
            
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
    
    def _extract_pdf_text(self, filepath):
        """Extract text from PDF file"""
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
        try:
            print(f"Processing file: {filepath}")
            print(f"File exists: {os.path.exists(filepath)}")
            result = self.ocr.ocr(filepath)
            print(f"PaddleOCR result: {result}")
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
            print(f"Extracted text: {text}")
            return text
        except Exception as e:
            print(f"PaddleOCR extraction error: {e}")
            return f"Error extracting text from image: {e}"