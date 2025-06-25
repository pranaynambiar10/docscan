import google.generativeai as genai
from PIL import Image
import io

class GeminiService:
    def __init__(self):
        self.model = None
        self._initialize_model()
    
    def _initialize_model(self):
        """Initialize the Gemini model"""
        try:
            self.model = genai.GenerativeModel('gemini-1.5-flash')
        except Exception as e:
            print(f"Error initializing Gemini model: {e}")
    
    def extract_invoice_data(self, file_path, mime_type):
        """Extracts data from an invoice using a specialized prompt."""
        try:
            if not self.model:
                return "AI service is not properly configured. Please check your API key."

            image_parts = []
            if "image" in mime_type:
                image_parts.append(Image.open(file_path))
            elif "pdf" in mime_type:
                # This is a placeholder for actual PDF processing to images
                # For a real implementation, you would use a library like pdf2image
                # to convert PDF pages to images.
                # For this example, we'll assume a dummy image if it's a PDF.
                # In a real scenario, you'd handle each page.
                print("PDF processing needs to be implemented. Using a placeholder.")
                # Creating a dummy blank image for demonstration
                dummy_image = Image.new('RGB', (100, 100), color = 'white')
                image_parts.append(dummy_image)


            prompt = """
You are an expert at extracting information from invoices.
From the provided invoice image, please extract the following information in JSON format:
- Invoice ID
- Vendor Name
- Customer Name
- Invoice Date
- Due Date
- Total Amount
- Line Items (as a list of objects, each with description, quantity, unit price, and total)

If a value is not found, use "N/A".
"""
            contents = {
                "parts": [
                    {"mime_type": mime_type, "data": image_parts[0]},
                    {"text": prompt}
                ]
            }

            # To handle images in gemini-pro-vision you need to send them as part of the content
            if "image" in mime_type:
                 img_byte_arr = io.BytesIO()
                 image_parts[0].save(img_byte_arr, format=image_parts[0].format or 'PNG')
                 img_byte_arr = img_byte_arr.getvalue()
                 contents = {
                     "parts": [
                         {"mime_type": mime_type, "data": img_byte_arr},
                         {"text": prompt}
                     ]
                 }


            response = self.model.generate_content(contents)
            return response.text

        except Exception as e:
            print(f"Gemini API error during invoice extraction: {e}")
            return "Sorry, I encountered an error while extracting invoice data."
    
    def get_response(self, question, document_content, filename):
        try:
            if not self.model:
                return "AI service is not properly configured. Please check your API key."

            prompt = f"""
You are an AI assistant helping users understand documents. 

Document Name: {filename}
Document Content:
{document_content[:5000]}...  

User Question: {question}

Please answer the user's question based on the document content provided. Be helpful, accurate, and concise. If the question cannot be answered from the document content, please say so clearly.

Answer:
"""

            response = self.model.generate_content(prompt)

            # 🛡️ Check for valid response
            if not response or not hasattr(response, 'text') or not response.text:
                print("⚠️ Gemini returned empty or invalid response.")
                return "AI did not return a response. Please try again."

            # 🔍 Debug log
            print(f"Gemini raw response: {response.text}")

            return response.text

        except Exception as e:
            print(f"Gemini API error: {e}")
            return "Sorry, I encountered an error while processing your question. Please try again."
    
    def analyze_document(self, document_content, filename):
        """Analyze document and provide a summary"""
        try:
            if not self.model:
                return "AI service is not properly configured."
            
            prompt = f"""
Please analyze this document and provide a brief summary:

Document Name: {filename}
Content: {document_content[:3000]}...

Please provide:
1. What type of document this appears to be
2. A brief summary of the main content
3. Key information or data points mentioned

Summary:
"""
            
            response = self.model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            print(f"Document analysis error: {e}")
            return "Could not analyze the document at this time."