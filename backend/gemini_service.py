import google.generativeai as genai

class GeminiService:
    def __init__(self):
        self.model = None
        self._initialize_model()
    
    def _initialize_model(self):
        """Initialize the Gemini model"""
        try:
            self.model = genai.GenerativeModel('gemini-pro')
        except Exception as e:
            print(f"Error initializing Gemini model: {e}")
    
    def get_response(self, question, document_content, filename):
        """Get AI response for a question about the document"""
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