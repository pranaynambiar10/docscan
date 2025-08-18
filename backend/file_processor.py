import os
import PyPDF2
import docx
from PIL import Image
import io
from paddleocr import PaddleOCR

class FileProcessor:
    def __init__(self, upload_folder):
        self.upload_folder = upload_folder
        # Initialize OCR immediately with robust error handling
        self.ocr = self._initialize_ocr()
        
    def _initialize_ocr(self):
        """Initialize PaddleOCR with robust error handling for server environments"""
        try:
            print("Initializing PaddleOCR...")
            # Initialize with minimal configuration for better compatibility
            ocr = PaddleOCR(
                lang='en', 
                use_gpu=False,  # Force CPU mode
                show_log=False,
                use_angle_cls=False,  # Disable angle classification for stability
                det_model_dir=None,
                rec_model_dir=None,
                cls_model_dir=None,
                drop_score=0.5  # Lower threshold for better text detection
            )
            print("PaddleOCR initialized successfully")
            return ocr
        except Exception as e:
            print(f"Failed to initialize PaddleOCR: {e}")
            # Return None instead of string to handle gracefully
            return None  
    
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
        """Extract text from image using PaddleOCR with robust error handling"""
        try:
            print(f"Processing image file: {filepath}")
            
            # Check if OCR is available
            if self.ocr is None:
                print("OCR not initialized, attempting to reinitialize...")
                self.ocr = self._initialize_ocr()
                
            if self.ocr is None:
                return "OCR service initialization failed. Please contact administrator."
            
            # Verify file exists and is readable
            if not os.path.exists(filepath):
                return "Image file not found."
                
            # Process the image with error handling
            try:
                result = self.ocr.ocr(filepath, cls=False)  # Disable classification for stability
                print(f"PaddleOCR result: {result}")
            except Exception as ocr_error:
                print(f"OCR processing error: {ocr_error}")
                return f"Failed to process image: {str(ocr_error)}"
            
            # Extract text from results
            text = ""
            if result and isinstance(result, list) and len(result) > 0:
                for page_result in result:
                    if page_result:  # Check if page result is not None
                        for line_result in page_result:
                            if line_result and len(line_result) >= 2:
                                # Extract text and confidence
                                bbox = line_result[0]  # Bounding box
                                text_info = line_result[1]  # Text and confidence
                                
                                if isinstance(text_info, (list, tuple)) and len(text_info) >= 2:
                                    text_piece = text_info[0]
                                    confidence = text_info[1]
                                    
                                    # Add text if confidence is good
                                    if isinstance(text_piece, str) and confidence > 0.5:
                                        text += text_piece + " "
            
            if not text.strip():
                return "No readable text found in this image. The image might be too blurry, have poor lighting, or contain no text."
                
            print(f"Successfully extracted {len(text.strip())} characters from image")
            return text.strip()
            
        except Exception as e:
            error_msg = f"Error processing image: {str(e)}"
            print(error_msg)
            return error_msg

    def test_ocr_status(self):
        """Test if OCR is working properly"""
        if self.ocr is None:
            return {"status": "failed", "message": "OCR not initialized"}
        
        try:
            # Simple test - this should not fail if OCR is properly initialized
            test_result = hasattr(self.ocr, 'ocr')
            if test_result:
                return {"status": "success", "message": "OCR is ready"}
            else:
                return {"status": "failed", "message": "OCR object invalid"}
        except Exception as e:
            return {"status": "error", "message": f"OCR test failed: {str(e)}"}