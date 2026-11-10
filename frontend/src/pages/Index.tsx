import React, { useState, useRef } from 'react';
import { Upload, X, Send, FileText, MessageCircle } from 'lucide-react';
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
  timestamp: Date;
  isLoading?: boolean;
  modelUsed?: string;
}

interface UploadedFile {
  name: string;
  size: number;
  type: string;
}

const Index = () => {
  const [uploadedFile, setUploadedFile] = useState<UploadedFile | null>(null);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      text: 'Upload a document to start asking questions about it.',
      sender: 'bot',
      timestamp: new Date()
    }
  ]);
  const [messageInput, setMessageInput] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const [isChatEnabled, setIsChatEnabled] = useState(false);
  const [modelTier, setModelTier] = useState<'auto' | 'fast' | 'deep'>('auto');
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

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
    return (bytes / 1024 / 1024).toFixed(2);
  };

  const handleFileSelect = (file: File) => {
    if (!isValidFile(file)) {
      toast.error('Please upload a valid file (PDF, TXT, DOC, DOCX, JPG, JPEG, PNG)');
      return;
    }

    processFile(file);
  };

  const processFile = async (file: File) => {
    // Set file info immediately to prevent blinking
    const fileInfo: UploadedFile = {
      name: file.name,
      size: file.size,
      type: file.type
    };
    setUploadedFile(fileInfo);
    setIsUploading(true);

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
        
        // Add success message
        const successMessage: Message = {
          id: Date.now().toString(),
          text: `Document "${file.name}" has been uploaded and processed. You can now ask questions about it!`,
          sender: 'bot',
          timestamp: new Date()
        };
        setMessages(prev => [...prev, successMessage]);
        
        setIsChatEnabled(true);
        toast.success('Document uploaded successfully!');
      } else {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Upload failed');
      }
    } catch (error) {
      console.error('Upload error:', error);
      
      // Remove loading message
      setMessages(prev => prev.filter(msg => !msg.isLoading));
      
      // Add error message but keep file info
      const errorMessage: Message = {
        id: Date.now().toString(),
        text: 'Error uploading file. Please try again.',
        sender: 'bot',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
      
      toast.error('Failed to upload document');
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
    setMessages([
      {
        id: '1',
        text: 'Upload a document to start asking questions about it.',
        sender: 'bot',
        timestamp: new Date()
      }
    ]);
    toast.info('File removed');
  };

  const sendMessage = async () => {
    const message = messageInput.trim();
    if (!message || !uploadedFile) return;

    // Add user message
    const userMessage: Message = {
      id: Date.now().toString(),
      text: message,
      sender: 'user',
      timestamp: new Date()
    };
    setMessages(prev => [...prev, userMessage]);
    setMessageInput('');

    // Add loading message
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

      // Remove loading message
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
        throw new Error('Failed to get response');
      }
    } catch (error) {
      console.error('Chat error:', error);
      
      // Remove loading message
      setMessages(prev => prev.filter(msg => !msg.isLoading));
      
      const errorMessage: Message = {
        id: Date.now().toString(),
        text: 'Error getting response. Please try again.',
        sender: 'bot',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
      
      toast.error('Failed to get AI response');
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
        <Card className="mb-8">
          <CardHeader className="text-center">
            <CardTitle className="text-3xl font-bold text-gray-800 mb-2">
              AI Document & Invoice Extraction Assistant
            </CardTitle>
            <p className="text-gray-600">Upload a document and ask questions about it</p>
          </CardHeader>
        </Card>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Upload Section */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Upload className="w-5 h-5" />
                Upload Document
              </CardTitle>
            </CardHeader>
            <CardContent>
              {!uploadedFile ? (
                <div
                  className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
                    dragOver ? 'border-blue-400 bg-blue-50' : 'border-gray-300 hover:border-blue-400'
                  }`}
                  onDrop={handleDrop}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onClick={() => fileInputRef.current?.click()}
                >
                  <FileText className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                  <p className="text-gray-600 mb-4">
                    Drag and drop your file here or click to browse
                  </p>
                  <Button type="button" disabled={isUploading}>
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
                    <div>
                      <p className="font-semibold text-green-800">
                        File: {uploadedFile.name}
                      </p>
                      <p className="text-sm text-green-600">
                        Size: {formatFileSize(uploadedFile.size)} MB
                      </p>
                      {isUploading && (
                        <p className="text-sm text-blue-600 animate-pulse">
                          Processing...
                        </p>
                      )}
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={removeFile}
                      className="text-red-600 hover:text-red-700"
                      disabled={isUploading}
                    >
                      <X className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Chat Section */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <CardTitle className="flex items-center gap-2 text-lg">
                <MessageCircle className="w-5 h-5" />
                Ask Questions
              </CardTitle>
              {/* Dual-Model Routing Selector */}
              <div className="flex items-center gap-1 bg-gray-100 p-1 rounded-lg text-xs">
                <button
                  type="button"
                  onClick={() => setModelTier('auto')}
                  className={`px-2.5 py-1 rounded-md font-medium transition-all ${
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
                  className={`px-2.5 py-1 rounded-md font-medium transition-all ${
                    modelTier === 'fast'
                      ? 'bg-white shadow text-green-600 font-semibold'
                      : 'text-gray-600 hover:text-gray-900'
                  }`}
                  title="Fast Mode: Uses qwen2.5:1.5b (<1 sec responses)"
                >
                  ⚡ Fast (1.5B)
                </button>
                <button
                  type="button"
                  onClick={() => setModelTier('deep')}
                  className={`px-2.5 py-1 rounded-md font-medium transition-all ${
                    modelTier === 'deep'
                      ? 'bg-white shadow text-purple-600 font-semibold'
                      : 'text-gray-600 hover:text-gray-900'
                  }`}
                  title="Deep Analysis: Uses qwen2.5:3b for complex multi-page reasoning"
                >
                  🎯 Deep (3B)
                </button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="h-96 flex flex-col">
                {/* Messages */}
                <div className="flex-1 overflow-y-auto border border-gray-200 rounded-lg p-4 mb-4 bg-gray-50">
                  {messages.map((message) => (
                    <div
                      key={message.id}
                      className={`mb-4 p-3 rounded-lg ${
                        message.sender === 'user'
                          ? 'bg-blue-500 text-white ml-auto max-w-[80%]'
                          : 'bg-white text-gray-800 mr-auto max-w-[80%] shadow-sm'
                      } ${message.isLoading ? 'italic text-gray-600' : ''}`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <p className="font-semibold text-xs opacity-75">
                          {message.sender === 'user' ? 'You' : 'AI'}
                        </p>
                        {message.modelUsed && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-50 text-blue-600 font-mono">
                            {message.modelUsed}
                          </span>
                        )}
                      </div>
                      <p className="text-sm whitespace-pre-wrap">{message.text}</p>
                    </div>
                  ))}
                </div>

                {/* Input Area */}
                <div className="flex gap-2">
                  <Input
                    value={messageInput}
                    onChange={(e) => setMessageInput(e.target.value)}
                    onKeyPress={handleKeyPress}
                    placeholder={
                      isChatEnabled ? 'Ask a question about your document...' : 'Upload a document first...'
                    }
                    disabled={!isChatEnabled}
                    className="flex-1"
                  />
                  <Button onClick={sendMessage} disabled={!isChatEnabled || !messageInput.trim()}>
                    <Send className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default Index;
