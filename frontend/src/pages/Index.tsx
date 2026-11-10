import React, { useState, useRef, useEffect } from 'react';
import { Upload, X, Send, FileText, MessageCircle, Trash2, Clock, CheckCircle2, RotateCcw, FolderOpen } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { toast } from 'sonner';

const API_BASE_URL = import.meta.env.VITE_API_URL || 
  (typeof window !== 'undefined' ? `${window.location.protocol}//${window.location.hostname}:5000` : 'http://localhost:5000');

interface Message {
  id: string;
  text: string;
  sender: 'user' | 'bot';
  timestamp: string | Date;
  isLoading?: boolean;
  modelUsed?: string;
}

interface UploadedFile {
  name: string;
  size: number;
  type: string;
}

interface DocumentMeta {
  filename: string;
  chunk_count: number;
  upload_time: string;
}

const DEFAULT_WELCOME_MSG: Message = {
  id: '1',
  text: 'Upload a document to start asking questions about it, or choose from previously uploaded documents below.',
  sender: 'bot',
  timestamp: new Date()
};

const Index = () => {
  const [uploadedFile, setUploadedFile] = useState<UploadedFile | null>(null);
  const [savedDocuments, setSavedDocuments] = useState<DocumentMeta[]>([]);
  const [messages, setMessages] = useState<Message[]>([DEFAULT_WELCOME_MSG]);
  const [messageInput, setMessageInput] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const [isChatEnabled, setIsChatEnabled] = useState(false);
  const [modelTier, setModelTier] = useState<'auto' | 'fast' | 'deep'>('auto');
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const validFileTypes = [
    'application/pdf',
    'text/plain',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'image/jpeg',
    'image/jpg',
    'image/png'
  ];

  const isValidFile = (file: File) => {
    return validFileTypes.includes(file.type);
  };

  const formatFileSize = (bytes: number) => {
    if (!bytes) return '0.00';
    return (bytes / 1024 / 1024).toFixed(2);
  };

  // ── 1. Fetch previously uploaded documents on load ─────────────────────────
  const fetchDocuments = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/documents`);
      if (res.ok) {
        const docs: DocumentMeta[] = await res.json();
        setSavedDocuments(docs);
      }
    } catch (err) {
      console.warn('Could not fetch previous documents:', err);
    }
  };

  // ── 2. Restore active document & chat on page refresh ──────────────────────
  useEffect(() => {
    fetchDocuments();

    try {
      const savedDoc = localStorage.getItem('docscan_active_doc');
      if (savedDoc) {
        const parsedDoc: UploadedFile = JSON.parse(savedDoc);
        setUploadedFile(parsedDoc);
        setIsChatEnabled(true);

        const savedChat = localStorage.getItem(`docscan_chat_${parsedDoc.name}`);
        if (savedChat) {
          const parsedChat: Message[] = JSON.parse(savedChat);
          if (parsedChat.length > 0) {
            setMessages(parsedChat);
            return;
          }
        }

        setMessages([
          {
            id: '1',
            text: `Document "${parsedDoc.name}" is loaded from memory. You can continue asking questions!`,
            sender: 'bot',
            timestamp: new Date()
          }
        ]);
      }
    } catch (err) {
      console.error('Error restoring localStorage session:', err);
    }
  }, []);

  // ── 3. Save chat history whenever messages change ──────────────────────────
  useEffect(() => {
    if (uploadedFile && messages.length > 0) {
      try {
        localStorage.setItem(`docscan_chat_${uploadedFile.name}`, JSON.stringify(messages));
      } catch (e) {
        console.warn('Could not save chat to localStorage:', e);
      }
    }
    // Auto-scroll to bottom of chat
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, uploadedFile]);

  // ── Switch to a previously uploaded document ──────────────────────────────
  const selectDocument = (doc: DocumentMeta) => {
    const fileInfo: UploadedFile = {
      name: doc.filename,
      size: 0,
      type: doc.filename.endsWith('.pdf') ? 'application/pdf' : 'text/plain'
    };

    setUploadedFile(fileInfo);
    setIsChatEnabled(true);
    localStorage.setItem('docscan_active_doc', JSON.stringify(fileInfo));

    // Restore chat history for this specific document
    const savedChat = localStorage.getItem(`docscan_chat_${doc.filename}`);
    if (savedChat) {
      try {
        const parsed = JSON.parse(savedChat);
        if (parsed.length > 0) {
          setMessages(parsed);
          toast.success(`Switched to "${doc.filename}"`);
          return;
        }
      } catch (e) {}
    }

    setMessages([
      {
        id: Date.now().toString(),
        text: `Switched to "${doc.filename}" (${doc.chunk_count || 1} RAG chunks). What would you like to know?`,
        sender: 'bot',
        timestamp: new Date()
      }
    ]);
    toast.success(`Switched to "${doc.filename}"`);
  };

  // ── Delete a document ──────────────────────────────────────────────────────
  const deleteDocument = async (filename: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm(`Are you sure you want to delete "${filename}"?`)) return;

    try {
      const res = await fetch(`${API_BASE_URL}/documents/${encodeURIComponent(filename)}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        setSavedDocuments(prev => prev.filter(d => d.filename !== filename));
        localStorage.removeItem(`docscan_chat_${filename}`);

        if (uploadedFile?.name === filename) {
          removeFile();
        }
        toast.success(`Deleted "${filename}"`);
      } else {
        toast.error('Failed to delete document');
      }
    } catch (err) {
      toast.error('Error connecting to backend to delete document');
    }
  };

  const handleFileSelect = (file: File) => {
    if (!isValidFile(file)) {
      toast.error('Please upload a valid file (PDF, TXT, DOC, DOCX, JPG, JPEG, PNG)');
      return;
    }

    processFile(file);
  };

  const processFile = async (file: File) => {
    const fileInfo: UploadedFile = {
      name: file.name,
      size: file.size,
      type: file.type
    };
    setUploadedFile(fileInfo);
    setIsUploading(true);

    // Save active document in localStorage
    localStorage.setItem('docscan_active_doc', JSON.stringify(fileInfo));

    // Add loading message
    const loadingMessage: Message = {
      id: Date.now().toString(),
      text: 'Uploading and processing your document...',
      sender: 'bot',
      timestamp: new Date(),
      isLoading: true
    };
    setMessages(prev => [...prev, loadingMessage]);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch(`${API_BASE_URL}/upload`, {
        method: 'POST',
        body: formData
      });

      // Remove loading message
      setMessages(prev => prev.filter(msg => !msg.isLoading));

      if (response.ok) {
        const result = await response.json();
        
        const chunkInfo = result.chunk_count ? ` (${result.chunk_count} vector chunks indexed for RAG)` : '';
        const successMessage: Message = {
          id: Date.now().toString(),
          text: `Document "${file.name}" has been uploaded and processed successfully${chunkInfo}. You can now ask questions!`,
          sender: 'bot',
          timestamp: new Date()
        };
        setMessages([successMessage]);
        
        setIsChatEnabled(true);
        toast.success('Document uploaded and indexed successfully!');
        fetchDocuments(); // Refresh document list
      } else {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `Upload failed with server error ${response.status}`);
      }
    } catch (error: any) {
      console.error('Upload error:', error);
      
      setMessages(prev => prev.filter(msg => !msg.isLoading));
      
      const errorMsg = error?.message || 'Error uploading file. Please try again.';
      const errorMessage: Message = {
        id: Date.now().toString(),
        text: `Error uploading file: ${errorMsg}`,
        sender: 'bot',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
      
      toast.error(`Upload failed: ${errorMsg}`);
    } finally {
      setIsUploading(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFileSelect(files[0]);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
  };

  const removeFile = () => {
    setUploadedFile(null);
    setIsChatEnabled(false);
    localStorage.removeItem('docscan_active_doc');
    setMessages([DEFAULT_WELCOME_MSG]);
    toast.info('Document deselected');
  };

  const clearChat = () => {
    if (!uploadedFile) return;
    localStorage.removeItem(`docscan_chat_${uploadedFile.name}`);
    setMessages([
      {
        id: Date.now().toString(),
        text: `Chat cleared for "${uploadedFile.name}". Ask a new question!`,
        sender: 'bot',
        timestamp: new Date()
      }
    ]);
    toast.info('Chat history cleared');
  };

  const sendMessage = async () => {
    const message = messageInput.trim();
    if (!message || !uploadedFile) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      text: message,
      sender: 'user',
      timestamp: new Date()
    };
    setMessages(prev => [...prev, userMessage]);
    setMessageInput('');

    const loadingMessage: Message = {
      id: (Date.now() + 1).toString(),
      text: 'Thinking...',
      sender: 'bot',
      timestamp: new Date(),
      isLoading: true
    };
    setMessages(prev => [...prev, loadingMessage]);

    try {
      const response = await fetch(`${API_BASE_URL}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: message,
          filename: uploadedFile.name,
          model_tier: modelTier,
        })
      });

      setMessages(prev => prev.filter(msg => !msg.isLoading));

      if (response.ok) {
        const result = await response.json();
        const botMessage: Message = {
          id: Date.now().toString(),
          text: result.response,
          sender: 'bot',
          timestamp: new Date(),
          modelUsed: result.model_used
        };
        setMessages(prev => [...prev, botMessage]);
      } else {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `Server returned error ${response.status}`);
      }
    } catch (error: any) {
      console.error('Chat error:', error);
      
      setMessages(prev => prev.filter(msg => !msg.isLoading));
      
      const errorMsg = error?.message || 'Error getting response. Please try again.';
      const errorMessage: Message = {
        id: Date.now().toString(),
        text: `Error getting AI response: ${errorMsg}`,
        sender: 'bot',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
      
      toast.error(`Chat error: ${errorMsg}`);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      sendMessage();
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-4">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <Card className="mb-6">
          <CardHeader className="text-center py-4">
            <CardTitle className="text-2xl font-bold text-gray-800">
              AI Document & Invoice Extraction Assistant
            </CardTitle>
            <p className="text-sm text-gray-600">Upload documents, extract with OCR, and ask questions with local RAG</p>
          </CardHeader>
        </Card>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left Column: Upload & Saved Documents */}
          <div className="space-y-6">
            {/* Upload Section */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-lg">
                  <Upload className="w-5 h-5 text-blue-600" />
                  Upload Document
                </CardTitle>
              </CardHeader>
              <CardContent>
                {!uploadedFile ? (
                  <div
                    className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${
                      dragOver ? 'border-blue-400 bg-blue-50' : 'border-gray-300 hover:border-blue-400'
                    }`}
                    onDrop={handleDrop}
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <FileText className="w-10 h-10 text-gray-400 mx-auto mb-3" />
                    <p className="text-sm text-gray-600 mb-3">
                      Drag and drop your file here or click to browse
                    </p>
                    <Button type="button" size="sm" disabled={isUploading}>
                      {isUploading ? 'Processing...' : 'Choose File'}
                    </Button>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".pdf,.txt,.doc,.docx,.jpg,.jpeg,.png"
                      onChange={(e) => e.target.files?.[0] && handleFileSelect(e.target.files[0])}
                      className="hidden"
                    />
                  </div>
                ) : (
                  <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-start gap-3">
                        <CheckCircle2 className="w-5 h-5 text-green-600 mt-0.5 flex-shrink-0" />
                        <div>
                          <p className="font-semibold text-green-900 text-sm break-all">
                            {uploadedFile.name}
                          </p>
                          {uploadedFile.size > 0 && (
                            <p className="text-xs text-green-700">
                              Size: {formatFileSize(uploadedFile.size)} MB
                            </p>
                          )}
                          <p className="text-[11px] text-green-600 mt-1">
                            Active Document (Chat enabled)
                          </p>
                          {isUploading && (
                            <p className="text-xs text-blue-600 animate-pulse mt-1">
                              Processing & indexing...
                            </p>
                          )}
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={removeFile}
                        className="text-gray-500 hover:text-red-600"
                        disabled={isUploading}
                        title="Deselect document"
                      >
                        <X className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Previously Uploaded Documents */}
            <Card>
              <CardHeader className="pb-3 flex flex-row items-center justify-between">
                <CardTitle className="flex items-center gap-2 text-base font-semibold text-gray-800">
                  <FolderOpen className="w-4 h-4 text-indigo-600" />
                  Your Documents ({savedDocuments.length})
                </CardTitle>
                <Button variant="ghost" size="sm" onClick={fetchDocuments} className="text-xs text-gray-500 h-7">
                  Refresh
                </Button>
              </CardHeader>
              <CardContent className="pt-0">
                {savedDocuments.length === 0 ? (
                  <p className="text-xs text-gray-500 italic py-2 text-center">
                    No documents uploaded yet. Upload one above!
                  </p>
                ) : (
                  <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                    {savedDocuments.map((doc) => {
                      const isActive = uploadedFile?.name === doc.filename;
                      return (
                        <div
                          key={doc.filename}
                          onClick={() => selectDocument(doc)}
                          className={`p-2.5 rounded-lg border text-xs cursor-pointer transition-all flex items-center justify-between ${
                            isActive
                              ? 'bg-blue-50 border-blue-400 shadow-sm'
                              : 'bg-white border-gray-200 hover:border-blue-300 hover:bg-gray-50'
                          }`}
                        >
                          <div className="flex items-center gap-2.5 min-w-0 pr-2">
                            <FileText className={`w-4 h-4 flex-shrink-0 ${isActive ? 'text-blue-600' : 'text-gray-400'}`} />
                            <div className="min-w-0">
                              <p className={`font-medium truncate ${isActive ? 'text-blue-900 font-semibold' : 'text-gray-800'}`}>
                                {doc.filename}
                              </p>
                              <div className="flex items-center gap-2 text-[10px] text-gray-500 mt-0.5">
                                <span>{doc.chunk_count || 1} RAG chunks</span>
                                {doc.upload_time && (
                                  <>
                                    <span>•</span>
                                    <span>{new Date(doc.upload_time).toLocaleDateString()}</span>
                                  </>
                                )}
                              </div>
                            </div>
                          </div>

                          <div className="flex items-center gap-1.5 flex-shrink-0">
                            {isActive ? (
                              <span className="px-2 py-0.5 text-[10px] font-semibold text-blue-700 bg-blue-100 rounded-full">
                                Active
                              </span>
                            ) : (
                              <Button
                                variant="outline"
                                size="sm"
                                className="h-6 px-2 text-[11px] text-blue-600 hover:bg-blue-50"
                              >
                                Chat
                              </Button>
                            )}
                            <button
                              type="button"
                              onClick={(e) => deleteDocument(doc.filename, e)}
                              className="p-1 text-gray-400 hover:text-red-600 rounded transition-colors"
                              title="Delete document"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Right Column: Chat Section */}
          <Card className="flex flex-col h-[580px]">
            <CardHeader className="flex flex-row items-center justify-between pb-3 flex-shrink-0">
              <div className="flex items-center gap-2">
                <MessageCircle className="w-5 h-5 text-indigo-600" />
                <CardTitle className="text-base font-semibold">
                  Ask Questions
                </CardTitle>
                {uploadedFile && (
                  <span className="text-xs text-gray-500 truncate max-w-[150px]" title={uploadedFile.name}>
                    ({uploadedFile.name})
                  </span>
                )}
              </div>

              <div className="flex items-center gap-2">
                {/* Clear Chat Button */}
                {uploadedFile && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={clearChat}
                    className="h-7 px-2 text-xs text-gray-500 hover:text-gray-800"
                    title="Clear chat for this document"
                  >
                    <RotateCcw className="w-3 h-3 mr-1" />
                    Clear
                  </Button>
                )}

                {/* Dual-Model Routing Selector */}
                <div className="flex items-center gap-1 bg-gray-100 p-1 rounded-lg text-xs">
                  <button
                    type="button"
                    onClick={() => setModelTier('auto')}
                    className={`px-2 py-0.5 rounded-md font-medium text-[11px] transition-all ${
                      modelTier === 'auto'
                        ? 'bg-white shadow text-blue-600 font-semibold'
                        : 'text-gray-600 hover:text-gray-900'
                    }`}
                    title="Auto: Small bills use 1.5B (<1s), large docs use 3B with RAG"
                  >
                    🤖 Auto
                  </button>
                  <button
                    type="button"
                    onClick={() => setModelTier('fast')}
                    className={`px-2 py-0.5 rounded-md font-medium text-[11px] transition-all ${
                      modelTier === 'fast'
                        ? 'bg-white shadow text-green-600 font-semibold'
                        : 'text-gray-600 hover:text-gray-900'
                    }`}
                    title="Fast: Uses qwen2.5:1.5b (<1 sec responses)"
                  >
                    ⚡ 1.5B
                  </button>
                  <button
                    type="button"
                    onClick={() => setModelTier('deep')}
                    className={`px-2 py-0.5 rounded-md font-medium text-[11px] transition-all ${
                      modelTier === 'deep'
                        ? 'bg-white shadow text-purple-600 font-semibold'
                        : 'text-gray-600 hover:text-gray-900'
                    }`}
                    title="Deep: Uses qwen2.5:3b for multi-page reasoning"
                  >
                    🎯 3B
                  </button>
                </div>
              </div>
            </CardHeader>

            <CardContent className="flex-1 flex flex-col p-4 pt-0 min-h-0">
              {/* Messages Area */}
              <div className="flex-1 overflow-y-auto border border-gray-200 rounded-lg p-3 mb-3 bg-gray-50 space-y-3">
                {messages.map((message) => (
                  <div
                    key={message.id}
                    className={`p-3 rounded-lg text-sm ${
                      message.sender === 'user'
                        ? 'bg-blue-600 text-white ml-auto max-w-[85%]'
                        : 'bg-white text-gray-800 mr-auto max-w-[85%] shadow-sm border border-gray-100'
                    } ${message.isLoading ? 'italic text-gray-600' : ''}`}
                  >
                    <div className="flex items-center justify-between mb-1 gap-2">
                      <p className="font-semibold text-xs opacity-80">
                        {message.sender === 'user' ? 'You' : 'AI'}
                      </p>
                      {message.modelUsed && (
                        <span className="text-[10px] px-1.5 py-0.2 rounded bg-blue-50 text-blue-600 font-mono">
                          {message.modelUsed}
                        </span>
                      )}
                    </div>
                    <p className="whitespace-pre-wrap leading-relaxed">{message.text}</p>
                  </div>
                ))}
                <div ref={messagesEndRef} />
              </div>

              {/* Chat Input Area */}
              <div className="flex gap-2 flex-shrink-0">
                <Input
                  value={messageInput}
                  onChange={(e) => setMessageInput(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder={
                    isChatEnabled
                      ? `Ask a question about ${uploadedFile?.name}...`
                      : 'Upload or select a document first...'
                  }
                  disabled={!isChatEnabled || isUploading}
                  className="flex-1 text-sm"
                />
                <Button
                  onClick={sendMessage}
                  disabled={!isChatEnabled || !messageInput.trim() || isUploading}
                  size="sm"
                  className="px-4"
                >
                  <Send className="w-4 h-4" />
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default Index;
