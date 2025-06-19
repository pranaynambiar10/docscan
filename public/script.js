let uploadedFile = null;
const API_BASE_URL = 'http://localhost:5000';

// DOM elements
const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const fileInfo = document.getElementById('fileInfo');
const fileName = document.getElementById('fileName');
const messages = document.getElementById('messages');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');

// File upload handling
uploadArea.addEventListener('click', () => fileInput.click());
uploadArea.addEventListener('dragover', handleDragOver);
uploadArea.addEventListener('dragleave', handleDragLeave);
uploadArea.addEventListener('drop', handleDrop);
fileInput.addEventListener('change', handleFileSelect);
messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});

function handleDragOver(e) {
    e.preventDefault();
    uploadArea.classList.add('dragover');
}

function handleDragLeave(e) {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
}

function handleDrop(e) {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        processFile(files[0]);
    }
}

function handleFileSelect(e) {
    const file = e.target.files[0];
    if (file) {
        processFile(file);
    }
}

async function processFile(file) {
    if (!isValidFile(file)) {
        alert('Please upload a valid file (PDF, TXT, DOC, DOCX, JPG, JPEG, PNG)');
        return;
    }

    uploadedFile = file;
    showFileInfo(file);
    
    // Upload file to backend
    try {
        addMessage('Uploading and processing your document...', 'bot', true);
        
        const formData = new FormData();
        formData.append('file', file);
        
        const response = await fetch(`${API_BASE_URL}/upload`, {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            const result = await response.json();
            clearLoadingMessage();
            addMessage(`Document "${file.name}" has been uploaded and processed. You can now ask questions about it!`, 'bot');
            enableChat();
        } else {
            clearLoadingMessage();
            addMessage('Error uploading file. Please try again.', 'bot');
        }
    } catch (error) {
        clearLoadingMessage();
        addMessage('Error connecting to server. Please try again.', 'bot');
        console.error('Upload error:', error);
    }
}

function isValidFile(file) {
    const validTypes = [
        'application/pdf',
        'text/plain',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'image/jpeg',
        'image/jpg',
        'image/png'
    ];
    return validTypes.includes(file.type);
}

function showFileInfo(file) {
    fileName.textContent = `File: ${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)`;
    fileInfo.style.display = 'block';
    uploadArea.style.display = 'none';
}

function removeFile() {
    uploadedFile = null;
    fileInfo.style.display = 'none';
    uploadArea.style.display = 'block';
    disableChat();
    
    // Clear messages except the initial one
    messages.innerHTML = `
        <div class="message bot-message">
            <strong>AI:</strong> Upload a document to start asking questions about it.
        </div>
    `;
}

function enableChat() {
    messageInput.disabled = false;
    sendBtn.disabled = false;
    messageInput.placeholder = 'Ask a question about your document...';
}

function disableChat() {
    messageInput.disabled = true;
    sendBtn.disabled = true;
    messageInput.placeholder = 'Upload a document first...';
}

async function sendMessage() {
    const message = messageInput.value.trim();
    if (!message || !uploadedFile) return;
    
    addMessage(message, 'user');
    messageInput.value = '';
    
    // Add loading message
    addMessage('Thinking...', 'bot', true);
    
    try {
        const response = await fetch(`${API_BASE_URL}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: message,
                filename: uploadedFile.name
            })
        });
        
        if (response.ok) {
            const result = await response.json();
            clearLoadingMessage();
            addMessage(result.response, 'bot');
        } else {
            clearLoadingMessage();
            addMessage('Error getting response. Please try again.', 'bot');
        }
    } catch (error) {
        clearLoadingMessage();
        addMessage('Error connecting to server. Please try again.', 'bot');
        console.error('Chat error:', error);
    }
}

function addMessage(text, sender, isLoading = false) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}-message ${isLoading ? 'loading' : ''}`;
    messageDiv.innerHTML = `<strong>${sender === 'user' ? 'You' : 'AI'}:</strong> ${text}`;
    
    if (isLoading) {
        messageDiv.id = 'loadingMessage';
    }
    
    messages.appendChild(messageDiv);
    messages.scrollTop = messages.scrollHeight;
}

function clearLoadingMessage() {
    const loadingMessage = document.getElementById('loadingMessage');
    if (loadingMessage) {
        loadingMessage.remove();
    }
}
