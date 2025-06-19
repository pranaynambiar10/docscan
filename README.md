# AI Document Assistant

A simple AI-powered document analysis platform that allows users to upload documents and ask questions about them using Google's Gemini AI.

## Features

- Upload PDF, TXT, DOC, DOCX, and image files
- Ask questions about uploaded documents
- Get AI-powered responses using Google Gemini
- Simple, beginner-friendly interface

## Setup Instructions

### Backend Setup (Python)

1. **Install Python** (3.8 or higher)

2. **Navigate to backend directory**:
   ```bash
   cd backend
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Get Gemini API Key**:
   - Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
   - Create a new API key
   - Copy the API key

5. **Configure API Key**:
   - create a .env file in main folder
   - write "GEMINI_API_KEY=YOUR_GEMINI_API_KEY_HERE"
   - Replace `YOUR_GEMINI_API_KEY_HERE` with your actual API key

6. **Run the backend**:
   ```bash
   python app.py
   ```

The backend will start on `http://localhost:5000`

### Frontend Setup

1. **Serve the frontend**:
   - You can use any simple HTTP server
   - For Python: `python -m http.server 8000` (from the `public` directory)
   - Or open `public/index.html` directly in your browser

2. **Access the application**:
   - Open your browser and go to `http://localhost:8000`
   - Or open the `index.html` file directly

## How to Use

1. **Upload a Document**: Drag and drop or click to select a PDF, text, or Word document
2. **Wait for Processing**: The system will extract text from your document
3. **Ask Questions**: Type questions about your document in the chat interface
4. **Get AI Responses**: The Gemini AI will analyze your document and provide answers

## File Structure

```
├── public/
│   ├── index.html      # Main HTML file
│   ├── style.css       # Styling
│   └── script.js       # Frontend JavaScript
├── backend/
│   ├── app.py          # Main Flask application
│   ├── file_processor.py   # File processing utilities
│   ├── gemini_service.py   # Gemini AI integration
│   └── requirements.txt    # Python dependencies
└── README.md
    .env
```

## Troubleshooting

- **CORS Issues**: Make sure the backend is running on port 5000
- **File Upload Fails**: Check file size and format
- **AI Not Responding**: Verify your Gemini API key is correct
- **Database Issues**: The SQLite database will be created automatically

## Future Enhancements

- Add user authentication
- Support for more file types
- Better OCR for images
- Document storage in cloud
- Improved UI/UX
