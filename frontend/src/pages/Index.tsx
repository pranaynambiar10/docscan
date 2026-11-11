import React, { useState, useRef, useEffect } from 'react';
import { 
  Upload, X, Send, FileText, MessageCircle, Trash2, CheckCircle2, 
  RotateCcw, FolderOpen, Eye, Search, Copy, Check, ChevronDown, ChevronUp, FileSearch, Sparkles, BookOpen
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toast } from 'sonner';

const API_BASE_URL = import.meta.env.VITE_API_URL || 
  (typeof window !== 'undefined' ? `${window.location.protocol}//${window.location.hostname}:5000` : 'http://localhost:5000');

export interface MatchedSection {
  section_id?: string;
  section_title: string;
  parent_title?: string;
  page_range?: string;
  full_text?: string;
}

export interface SectionMeta {
  id: number;
  section_id: string;
  section_index: number;
  section_title: string;
  parent_title: string;
  page_start: number;
  page_end: number;
  content_length: number;
}

interface Message {
  id: string;
  text: string;
  sender: 'user' | 'bot';
  timestamp: string | Date;
  isLoading?: boolean;
  modelUsed?: string;
  sources?: string[];
  fullDocUsed?: boolean;
  retrievalMode?: string;
  matchedSection?: MatchedSection | null;
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
  const [modelTier, setModelTier] = useState<'auto' | 'fast' | 'deep' | 'full'>('auto');
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Full Document Viewer State
  const [isViewerOpen, setIsViewerOpen] = useState(false);
  const [viewerFilename, setViewerFilename] = useState('');
  const [viewerContent, setViewerContent] = useState('');
  const [viewerLoading, setViewerLoading] = useState(false);
  const [viewerSearch, setViewerSearch] = useState('');
  const [hasCopied, setHasCopied] = useState(false);
  const [expandedSources, setExpandedSources] = useState<{ [msgId: string]: boolean }>({});

  // Full Section Viewer State
  const [activeSectionModal, setActiveSectionModal] = useState<MatchedSection | null>(null);
  const [hasCopiedSection, setHasCopiedSection] = useState(false);

  // Sections Explorer State
  const [isSectionsExplorerOpen, setIsSectionsExplorerOpen] = useState(false);
  const [sectionsTargetDoc, setSectionsTargetDoc] = useState('');
  const [sectionsList, setSectionsList] = useState<SectionMeta[]>([]);
  const [sectionsLoading, setSectionsLoading] = useState(false);
  const [sectionsSearch, setSectionsSearch] = useState('');

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
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, uploadedFile]);

  // ── Open Full Text Viewer ──────────────────────────────────────────────────
  const openFullTextViewer = async (filename?: string) => {
    const target = filename || uploadedFile?.name;
    if (!target) return;

    setViewerFilename(target);
    setIsViewerOpen(true);
    setViewerLoading(true);
    setViewerSearch('');
    setHasCopied(false);

    try {
      const res = await fetch(`${API_BASE_URL}/documents/${encodeURIComponent(target)}/content`);
      if (res.ok) {
        const data = await res.json();
        setViewerContent(data.content || 'No text content found in document.');
      } else {
        setViewerContent('Failed to load document text from server.');
      }
    } catch (err) {
      setViewerContent('Error connecting to backend to fetch document content.');
    } finally {
      setViewerLoading(false);
    }
  };

  const copyFullText = () => {
    if (!viewerContent) return;
    navigator.clipboard.writeText(viewerContent);
    setHasCopied(true);
    toast.success('Document text copied to clipboard!');
    setTimeout(() => setHasCopied(false), 2000);
  };

  const toggleSource = (msgId: string) => {
    setExpandedSources(prev => ({ ...prev, [msgId]: !prev[msgId] }));
  };

  // ── Section Explorer & Viewer Helpers ─────────────────────────────────────
  const openSectionsExplorer = async (filename: string) => {
    setSectionsTargetDoc(filename);
    setIsSectionsExplorerOpen(true);
    setSectionsLoading(true);
    setSectionsSearch('');
    try {
      const res = await fetch(`${API_BASE_URL}/documents/${encodeURIComponent(filename)}/sections`);
      if (res.ok) {
        const data = await res.json();
        setSectionsList(data.sections || []);
      } else {
        toast.error('Failed to load sections from backend');
      }
    } catch (e) {
      toast.error('Network error loading document sections');
    } finally {
      setSectionsLoading(false);
    }
  };

  const viewSectionDetail = async (sec: SectionMeta) => {
    try {
      const res = await fetch(`${API_BASE_URL}/documents/${encodeURIComponent(sectionsTargetDoc)}/sections/${encodeURIComponent(sec.section_id)}`);
      if (res.ok) {
        const data = await res.json();
        setActiveSectionModal({
          section_id: data.section_id,
          section_title: data.section_title,
          parent_title: data.parent_title,
          page_range: data.page_start === data.page_end ? `Page ${data.page_start}` : `Pages ${data.page_start}–${data.page_end}`,
          full_text: data.content
        });
      }
    } catch (e) {
      toast.error('Failed to load section content');
    }
  };

  const copySectionText = async () => {
    if (!activeSectionModal?.full_text) return;
    try {
      await navigator.clipboard.writeText(activeSectionModal.full_text);
      setHasCopiedSection(true);
      toast.success('Complete section text copied to clipboard!');
      setTimeout(() => setHasCopiedSection(false), 2000);
    } catch (e) {
      toast.error('Could not copy to clipboard');
    }
  };

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

    localStorage.setItem('docscan_active_doc', JSON.stringify(fileInfo));

    const loadingMessage: Message = {
      id: Date.now().toString(),
      text: 'Uploading, extracting text, and generating RAG vector embeddings...',
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

      setMessages(prev => prev.filter(msg => !msg.isLoading));

      if (response.ok) {
        const result = await response.json();
        
        const chunkInfo = result.chunk_count ? ` (${result.chunk_count} vector chunks indexed for RAG)` : '';
        const successMessage: Message = {
          id: Date.now().toString(),
          text: `Document "${file.name}" has been uploaded and indexed successfully${chunkInfo}. You can now ask questions about it, or switch to 📜 Full Doc mode if you need whole-document analysis!`,
          sender: 'bot',
          timestamp: new Date()
        };
        setMessages([successMessage]);
        
        setIsChatEnabled(true);
        toast.success('Document uploaded and indexed successfully!');
        fetchDocuments();
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
      text: modelTier === 'full' ? 'Analyzing entire document content...' : 'Searching vector index & thinking...',
      sender: 'bot',
      timestamp: new Date(),
      isLoading: true
    };
    setMessages(prev => [...prev, loadingMessage]);

    try {
      // Build context hint from recent messages to help section disambiguation
      const recentContext = messages
        .filter(m => m.sender === 'user' || (m.sender === 'bot' && m.matchedSection))
        .slice(-3)
        .map(m => m.sender === 'user' ? m.text : (m.matchedSection?.parent_title || ''))
        .join(' ');

      const response = await fetch(`${API_BASE_URL}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: message,
          filename: uploadedFile.name,
          model_tier: modelTier,
          context_hint: recentContext,
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
          modelUsed: result.model_used,
          sources: result.sources || [],
          fullDocUsed: result.full_doc_used || false,
          retrievalMode: result.retrieval_mode,
          matchedSection: result.matched_section || null,
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

  // Filtered viewer content based on search query
  const filteredLines = viewerContent
    ? viewerContent.split('\n').filter(line => 
        !viewerSearch.trim() || line.toLowerCase().includes(viewerSearch.toLowerCase())
      )
    : [];

  // Filtered sections in sections explorer
  const filteredSections = sectionsList.filter(s => {
    if (!sectionsSearch.trim()) return true;
    const term = sectionsSearch.toLowerCase();
    return (s.section_title && s.section_title.toLowerCase().includes(term)) ||
           (s.parent_title && s.parent_title.toLowerCase().includes(term));
  });

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-4">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <Card className="mb-6 shadow-sm border-blue-100">
          <CardHeader className="text-center py-4">
            <CardTitle className="text-2xl font-bold text-gray-800 flex items-center justify-center gap-2">
              <Sparkles className="w-6 h-6 text-blue-600" />
              AI Document & Invoice Extraction Assistant
            </CardTitle>
            <p className="text-sm text-gray-600">
              Upload documents, extract with OCR, and ask questions with local RAG & Full-Document intelligence
            </p>
          </CardHeader>
        </Card>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left Column: Upload & Saved Documents */}
          <div className="space-y-6">
            {/* Upload Section */}
            <Card className="shadow-sm">
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
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-start gap-3 min-w-0">
                        <CheckCircle2 className="w-5 h-5 text-green-600 mt-0.5 flex-shrink-0" />
                        <div className="min-w-0">
                          <p className="font-semibold text-green-900 text-sm break-all">
                            {uploadedFile.name}
                          </p>
                          {uploadedFile.size > 0 && (
                            <p className="text-xs text-green-700">
                              Size: {formatFileSize(uploadedFile.size)} MB
                            </p>
                          )}
                          <p className="text-[11px] text-green-600 mt-0.5 font-medium">
                            Active Document (Chat enabled)
                          </p>
                          {isUploading && (
                            <p className="text-xs text-blue-600 animate-pulse mt-1">
                              Processing & indexing...
                            </p>
                          )}

                          {/* Quick Actions for Active Document */}
                          <div className="flex items-center gap-2 mt-3">
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              onClick={() => openFullTextViewer()}
                              className="h-7 text-xs bg-white text-blue-700 border-blue-300 hover:bg-blue-50 font-medium"
                            >
                              <Eye className="w-3.5 h-3.5 mr-1" />
                              View Full Extracted Text
                            </Button>
                          </div>
                        </div>
                      </div>

                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={removeFile}
                        className="text-gray-500 hover:text-red-600 h-8 w-8 p-0"
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
            <Card className="shadow-sm">
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
                  <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
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
                            {/* Quick Browse Sections */}
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                openSectionsExplorer(doc.filename);
                              }}
                              className="p-1 text-gray-400 hover:text-indigo-600 rounded transition-colors"
                              title="Browse structured sections & modules"
                            >
                              <BookOpen className="w-3.5 h-3.5" />
                            </button>

                            {/* Quick View Text */}
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                openFullTextViewer(doc.filename);
                              }}
                              className="p-1 text-gray-400 hover:text-blue-600 rounded transition-colors"
                              title="Inspect full extracted text"
                            >
                              <Eye className="w-3.5 h-3.5" />
                            </button>

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
          <Card className="flex flex-col h-[600px] shadow-sm">
            <CardHeader className="flex flex-row items-center justify-between pb-3 flex-shrink-0">
              <div className="flex items-center gap-2 min-w-0">
                <MessageCircle className="w-5 h-5 text-indigo-600 flex-shrink-0" />
                <CardTitle className="text-base font-semibold truncate">
                  Ask Questions
                </CardTitle>
                {uploadedFile && (
                  <span className="text-xs text-gray-500 truncate max-w-[120px]" title={uploadedFile.name}>
                    ({uploadedFile.name})
                  </span>
                )}
              </div>

              <div className="flex items-center gap-1.5 flex-shrink-0">
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

                {/* Model & Analysis Mode Selector */}
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
                    title="Deep: Uses qwen2.5:3b for complex multi-page reasoning with RAG"
                  >
                    🎯 3B
                  </button>
                  <button
                    type="button"
                    onClick={() => setModelTier('full')}
                    className={`px-2 py-0.5 rounded-md font-medium text-[11px] transition-all ${
                      modelTier === 'full'
                        ? 'bg-amber-500 shadow text-white font-semibold'
                        : 'text-amber-800 hover:bg-amber-100'
                    }`}
                    title="Full Doc: Ingests the entire extracted document text without chunking (use when you need complete section context or full summaries)"
                  >
                    📜 Full Doc
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
                      <div className="flex items-center gap-1">
                        {message.fullDocUsed && (
                          <span className="text-[10px] px-1.5 py-0.2 rounded bg-amber-50 text-amber-700 border border-amber-200 font-medium">
                            📜 Full Doc
                          </span>
                        )}
                        {message.retrievalMode === 'full_section' && (
                          <span className="text-[10px] px-1.5 py-0.2 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 font-medium">
                            📜 Mode B: Full Section
                          </span>
                        )}
                        {message.retrievalMode === 'full_course' && (
                          <span className="text-[10px] px-1.5 py-0.2 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 font-medium">
                            📜 Mode B: Complete Syllabus
                          </span>
                        )}
                        {message.retrievalMode === 'rag' && (
                          <span className="text-[10px] px-1.5 py-0.2 rounded bg-blue-50 text-blue-700 border border-blue-200 font-medium">
                            🎯 Mode A: RAG Chunks
                          </span>
                        )}
                        {message.modelUsed && (
                          <span className="text-[10px] px-1.5 py-0.2 rounded bg-blue-50 text-blue-600 font-mono">
                            {message.modelUsed}
                          </span>
                        )}
                      </div>
                    </div>
                    
                    <p className="whitespace-pre-wrap leading-relaxed">{message.text}</p>

                    {/* View Full Section Button (Available whenever a source section is identified) */}
                    {message.matchedSection && (
                      <div className="mt-2 pt-2 border-t border-gray-100 flex items-center justify-between gap-2 flex-wrap">
                        <div className="flex items-center gap-1.5 text-xs text-gray-700 min-w-0">
                          <span className="font-semibold text-indigo-700 truncate max-w-[220px]">
                            📑 {message.matchedSection.section_title}
                          </span>
                          {message.matchedSection.page_range && (
                            <span className="text-[10px] bg-indigo-50 text-indigo-700 px-1.5 py-0.5 rounded border border-indigo-200 font-mono font-medium flex-shrink-0">
                              {message.matchedSection.page_range}
                            </span>
                          )}
                        </div>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setActiveSectionModal(message.matchedSection!)}
                          className="h-6 px-2 text-[11px] font-medium text-indigo-700 bg-indigo-50 border-indigo-200 hover:bg-indigo-100 flex items-center gap-1 transition-colors"
                        >
                          <Eye className="w-3 h-3" />
                          View Full Section
                        </Button>
                      </div>
                    )}

                    {/* Expandable Source Chunks (Available for RAG responses) */}
                    {message.sources && message.sources.length > 0 && (
                      <div className="mt-2.5 pt-2 border-t border-gray-100">
                        <button
                          type="button"
                          onClick={() => toggleSource(message.id)}
                          className="text-[11px] font-medium text-blue-600 hover:text-blue-800 flex items-center gap-1 transition-colors"
                        >
                          <FileSearch className="w-3.5 h-3.5" />
                          {expandedSources[message.id] ? (
                            <>
                              Hide retrieved context ({message.sources.length} chunks)
                              <ChevronUp className="w-3 h-3 ml-0.5" />
                            </>
                          ) : (
                            <>
                              View retrieved context ({message.sources.length} chunks used)
                              <ChevronDown className="w-3 h-3 ml-0.5" />
                            </>
                          )}
                        </button>

                        {expandedSources[message.id] && (
                          <div className="mt-2 space-y-2 text-left">
                            {message.sources.map((chunk, idx) => (
                              <div 
                                key={idx} 
                                className="bg-gray-50 border border-gray-200 rounded p-2 text-xs font-mono text-gray-700 whitespace-pre-wrap leading-normal"
                              >
                                <span className="font-bold text-[10px] text-blue-700 block mb-1">
                                  Context Chunk #{idx + 1}
                                </span>
                                {chunk}
                              </div>
                            ))}
                            <div className="flex items-center justify-between text-[11px] text-gray-500 pt-1">
                              <span>Need the complete section surrounding this?</span>
                              <button
                                type="button"
                                onClick={() => {
                                  setModelTier('full');
                                  toast.info('Switched to 📜 Full Doc mode. Ask your question again to query with the entire document!');
                                }}
                                className="text-amber-700 hover:underline font-semibold ml-2"
                              >
                                Switch to 📜 Full Doc mode →
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
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
                      ? modelTier === 'full'
                        ? `Ask anything using the entire document text...`
                        : `Ask a question about ${uploadedFile?.name}...`
                      : 'Upload or select a document first...'
                  }
                  disabled={!isChatEnabled || isUploading}
                  className="flex-1 text-sm"
                />
                <Button
                  onClick={sendMessage}
                  disabled={!isChatEnabled || !messageInput.trim() || isUploading}
                  size="sm"
                  className={`px-4 ${modelTier === 'full' ? 'bg-amber-600 hover:bg-amber-700' : ''}`}
                >
                  <Send className="w-4 h-4" />
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* ── Full Document Extracted Text Viewer Modal ──────────────────────── */}
      <Dialog open={isViewerOpen} onOpenChange={setIsViewerOpen}>
        <DialogContent className="max-w-3xl max-h-[85vh] flex flex-col p-6">
          <DialogHeader className="pb-3 border-b flex flex-row items-center justify-between">
            <div className="min-w-0 pr-4">
              <DialogTitle className="text-lg font-bold flex items-center gap-2 text-gray-900 truncate">
                <FileText className="w-5 h-5 text-blue-600 flex-shrink-0" />
                Full Extracted Text: {viewerFilename}
              </DialogTitle>
              <p className="text-xs text-gray-500 mt-1">
                {viewerContent.length} characters extracted via PyMuPDF / PaddleOCR
              </p>
            </div>
            
            <div className="flex items-center gap-2 flex-shrink-0">
              <Button
                variant="outline"
                size="sm"
                onClick={copyFullText}
                className="h-8 text-xs flex items-center gap-1.5"
                disabled={viewerLoading || !viewerContent}
              >
                {hasCopied ? (
                  <>
                    <Check className="w-3.5 h-3.5 text-green-600" />
                    Copied
                  </>
                ) : (
                  <>
                    <Copy className="w-3.5 h-3.5" />
                    Copy Text
                  </>
                )}
              </Button>
            </div>
          </DialogHeader>

          {/* Search bar inside text viewer */}
          <div className="py-2 flex items-center gap-2">
            <div className="relative flex-1">
              <Search className="w-4 h-4 absolute left-2.5 top-2.5 text-gray-400" />
              <Input
                value={viewerSearch}
                onChange={(e) => setViewerSearch(e.target.value)}
                placeholder="Search word or phrase inside extracted text..."
                className="pl-9 h-9 text-xs"
              />
            </div>
            {viewerSearch && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setViewerSearch('')}
                className="h-9 px-2 text-xs text-gray-500"
              >
                Clear
              </Button>
            )}
          </div>

          {/* Full Text Content Area */}
          <div className="flex-1 overflow-y-auto bg-gray-50 p-4 rounded-lg border border-gray-200 font-mono text-xs leading-relaxed text-gray-800 whitespace-pre-wrap select-text">
            {viewerLoading ? (
              <p className="text-center py-10 text-gray-500 animate-pulse font-sans">
                Loading extracted text from database...
              </p>
            ) : viewerSearch.trim() ? (
              filteredLines.length > 0 ? (
                filteredLines.map((line, i) => (
                  <div key={i} className="py-0.5 hover:bg-yellow-100 rounded px-1">
                    {line}
                  </div>
                ))
              ) : (
                <p className="text-gray-500 italic py-4 font-sans text-center">
                  No matching text found for "{viewerSearch}".
                </p>
              )
            ) : (
              viewerContent || <p className="text-gray-400 italic">No text extracted.</p>
            )}
          </div>

          {/* Modal Footer */}
          <div className="pt-3 border-t flex items-center justify-between text-xs text-gray-500">
            <span>
              💡 Tip: If RAG missed a detail, switch to <strong className="text-amber-800">📜 Full Doc</strong> mode in chat.
            </span>
            <Button
              size="sm"
              onClick={() => {
                setIsViewerOpen(false);
                setModelTier('full');
                toast.info('Switched to 📜 Full Doc mode! You can now ask questions about the entire document.');
              }}
              className="bg-amber-600 hover:bg-amber-700 text-white h-8 text-xs font-medium"
            >
              Analyze in 📜 Full Doc Mode
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* ── 2. Full Section Viewer Dialog (Dedicated Source Text Viewer) ──── */}
      <Dialog open={!!activeSectionModal} onOpenChange={(open) => !open && setActiveSectionModal(null)}>
        <DialogContent className="max-w-3xl max-h-[85vh] flex flex-col bg-white">
          <DialogHeader className="border-b pb-3">
            <div className="flex items-start justify-between pr-6">
              <div>
                <DialogTitle className="text-base font-bold text-gray-900 flex items-center gap-2">
                  <span className="text-indigo-600">📑</span> {activeSectionModal?.section_title}
                </DialogTitle>
                <div className="flex items-center gap-2 text-xs text-gray-500 mt-1">
                  {activeSectionModal?.parent_title && (
                    <span className="font-medium text-gray-700 truncate max-w-[360px]">{activeSectionModal.parent_title}</span>
                  )}
                  {activeSectionModal?.page_range && (
                    <>
                      <span>•</span>
                      <span className="px-1.5 py-0.5 bg-indigo-50 text-indigo-700 border border-indigo-200 rounded text-[11px] font-mono font-semibold">
                        {activeSectionModal.page_range}
                      </span>
                    </>
                  )}
                </div>
              </div>

              <Button
                variant="outline"
                size="sm"
                onClick={copySectionText}
                className="text-xs h-8 flex items-center gap-1.5 flex-shrink-0"
              >
                {hasCopiedSection ? (
                  <>
                    <Check className="w-3.5 h-3.5 text-green-600" />
                    Copied Section
                  </>
                ) : (
                  <>
                    <Copy className="w-3.5 h-3.5" />
                    Copy Full Section
                  </>
                )}
              </Button>
            </div>
          </DialogHeader>

          {/* Section Original Extracted Content */}
          <div className="flex-1 overflow-y-auto bg-gray-50 p-4 rounded-lg border border-gray-200 font-mono text-xs leading-relaxed text-gray-800 whitespace-pre-wrap select-text">
            {activeSectionModal?.full_text || 'No section text available.'}
          </div>

          {/* Section Modal Footer */}
          <div className="pt-2 border-t flex items-center justify-between text-xs text-gray-500">
            <span>
              ✅ Complete extracted source section (un-truncated original text).
            </span>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setActiveSectionModal(null)}
              className="text-xs h-7 text-gray-600 hover:text-gray-900"
            >
              Return to Chat
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* ── 3. Structured Sections Explorer Dialog ────────────────────────── */}
      <Dialog open={isSectionsExplorerOpen} onOpenChange={setIsSectionsExplorerOpen}>
        <DialogContent className="max-w-4xl max-h-[85vh] flex flex-col bg-white">
          <DialogHeader className="border-b pb-3">
            <div className="flex items-center justify-between pr-6">
              <div>
                <DialogTitle className="text-base font-bold text-gray-900 flex items-center gap-2">
                  <BookOpen className="w-4 h-4 text-indigo-600" />
                  Structured Sections & Modules
                </DialogTitle>
                <p className="text-xs text-gray-500 mt-0.5">
                  Document: <span className="font-semibold text-gray-700">{sectionsTargetDoc}</span> ({sectionsList.length} sections detected)
                </p>
              </div>
            </div>
          </DialogHeader>

          {/* Search Filter */}
          <div className="py-2 flex items-center gap-2">
            <div className="relative flex-1">
              <Search className="w-4 h-4 absolute left-2.5 top-2.5 text-gray-400" />
              <Input
                value={sectionsSearch}
                onChange={(e) => setSectionsSearch(e.target.value)}
                placeholder="Filter by section title, module number, or course name..."
                className="pl-9 h-9 text-xs"
              />
            </div>
            {sectionsSearch && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setSectionsSearch('')}
                className="h-9 px-2 text-xs text-gray-500"
              >
                Clear
              </Button>
            )}
          </div>

          {/* Sections List */}
          <div className="flex-1 overflow-y-auto space-y-1.5 pr-1">
            {sectionsLoading ? (
              <p className="text-center py-10 text-gray-500 animate-pulse text-xs">
                Loading structured sections...
              </p>
            ) : filteredSections.length === 0 ? (
              <p className="text-gray-500 italic py-6 text-center text-xs">
                No sections match "{sectionsSearch}".
              </p>
            ) : (
              filteredSections.map((sec) => (
                <div
                  key={sec.section_id}
                  className="p-2.5 rounded-lg border border-gray-200 hover:border-indigo-300 hover:bg-indigo-50/30 transition-all flex items-center justify-between gap-3 text-xs"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-gray-900 truncate">
                        {sec.section_title}
                      </span>
                      <span className="px-1.5 py-0.2 rounded bg-indigo-50 text-indigo-700 border border-indigo-200 font-mono text-[10px] flex-shrink-0 font-medium">
                        {sec.page_start === sec.page_end ? `Page ${sec.page_start}` : `Pages ${sec.page_start}–${sec.page_end}`}
                      </span>
                    </div>
                    {sec.parent_title && (
                      <p className="text-[11px] text-gray-500 truncate mt-0.5">
                        {sec.parent_title}
                      </p>
                    )}
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => viewSectionDetail(sec)}
                    className="h-7 text-xs text-indigo-700 bg-white hover:bg-indigo-50 border-indigo-200 flex items-center gap-1 flex-shrink-0"
                  >
                    <Eye className="w-3 h-3" />
                    View Text
                  </Button>
                </div>
              ))
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default Index;
