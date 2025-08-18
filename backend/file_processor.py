import os
import PyPDF2
import docx
from PIL import Image
import io
from paddleocr import PaddleOCR

class FileProcessor:
    def __init__(self, upload_folder):
        self.upload_folder = upload_folder
        self.ocr = None  # Lazy initialization
        
    def _initialize_ocr(self):
        """Initialize PaddleOCR with proper error handling"""
        if self.ocr is None:
            try:
                # Force CPU mode to avoid GPU context issues
                self.ocr = PaddleOCR(
                    lang='en', 
                    use_gpu=False,  # Force CPU mode for stability
                    show_log=False,  # Reduce logging
                    use_angle_cls=True,
                    det_model_dir=None,  # Use default models
                    rec_model_dir=None,
                    cls_model_dir=None
                )
                print("PaddleOCR initialized successfully")
            except Exception as e:
                print(f"Failed to initialize PaddleOCR: {e}")
                self.ocr = "failed"  # Mark as failed
        return self.ocr != "failed"  
    
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
        """Extract text from image using PaddleOCR with session independence"""
        try:
            print(f"Processing image file: {filepath}")
            
            # Initialize OCR if needed
            if not self._initialize_ocr():
                return "OCR service is not available. Please try again later."
            
            # Process the image
            result = self.ocr.ocr(filepath, cls=True)
            print(f"PaddleOCR result type: {type(result)}")
            
            text = ""
            if result and isinstance(result, list) and len(result) > 0:
                for line in result:
                    if line:  # Check if line is not None
                        for word_info in line:
                            if len(word_info) > 1 and isinstance(word_info[1], (list, tuple)):
                                text_piece = word_info[1][0]
                                confidence = word_info[1][1] if len(word_info[1]) > 1 else 1.0
                                # Only include text with good confidence
                                if isinstance(text_piece, str) and confidence > 0.6:
                                    text += text_piece + " "
            
            if not text.strip():
                return "No readable text found in this image."
                
            print(f"Successfully extracted {len(text)} characters")
            return text.strip()
            
        except Exception as e:
            error_msg = f"Error processing image: {str(e)}"
            print(error_msg)
            # Reset OCR for next attempt
            self.ocr = None
            return error_msg