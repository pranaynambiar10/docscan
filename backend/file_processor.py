
import os
import PyPDF2
import docx
from PIL import Image
import io

class FileProcessor:
    def __init__(self, upload_folder):
        self.upload_folder = upload_folder
    
    def process_file(self, file):
        """Process uploaded file and extract text content"""
        try:
            filename = file.filename
            filepath = os.path.join(self.upload_folder, filename)
            
            # Save the file
            file.save(filepath)
            
            # Extract text based on file type
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
        """Extract text from image using basic OCR (placeholder)"""
       
        return f"Image file uploaded: {os.path.basename(filepath)}. Image OCR processing would require additional setup with pytesseract."