"use client";

import React, { useState, useRef, useEffect } from "react";
import ReactMarkdown from 'react-markdown';

interface Message {
  id: string;
  sender: "user" | "ai";
  text: string;
  sources?: { title: string; url: string; source: string }[];
}

export default function Chatbot() {
  const [messages, setMessages] = useState<Message[]>([{
    id: "welcome",
    sender: "ai",
    text: "Chào bạn! Tôi là trợ lý AI của NewsPulse. Bạn muốn tôi tổng hợp thông tin hoặc trả lời câu hỏi gì từ các tin tức mới nhất?"
  }]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  // Auto scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim()) return;
    
    const userMsg: Message = {
      id: Date.now().toString(),
      sender: "user",
      text: input.trim()
    };
    
    setMessages(prev => [...prev, userMsg]);
    setInput("");
    setIsLoading(true);
    
    try {
      const res = await fetch("http://localhost:8000/api/v1/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMsg.text })
      });
      
      if (!res.ok) throw new Error("API error");
      
      const data = await res.json();
      
      const aiMsg: Message = {
        id: (Date.now() + 1).toString(),
        sender: "ai",
        text: data.answer,
        sources: data.context_sources
      };
      
      setMessages(prev => [...prev, aiMsg]);
    } catch (error) {
      console.error(error);
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        sender: "ai",
        text: "Xin lỗi, đã có lỗi xảy ra khi kết nối tới hệ thống AI. Vui lòng thử lại sau."
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-[600px] w-full bg-slate-900 rounded-xl overflow-hidden border border-slate-700 shadow-2xl">
      {/* Header */}
      <div className="bg-slate-800 p-4 border-b border-slate-700 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-blue-600 flex items-center justify-center text-white font-bold text-xl shadow-[0_0_15px_rgba(37,99,235,0.5)]">
            AI
          </div>
          <div>
            <h3 className="font-bold text-slate-100">NewsPulse RAG Assistant</h3>
            <p className="text-xs text-blue-400">Powered by Groq & Llama-3</p>
          </div>
        </div>
      </div>
      
      {/* Chat Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {messages.map(msg => (
          <div key={msg.id} className={`flex ${msg.sender === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[80%] rounded-2xl p-4 ${msg.sender === "user" ? "bg-blue-600 text-white rounded-br-none" : "bg-slate-800 text-slate-200 rounded-bl-none border border-slate-700 shadow-lg"}`}>
              {msg.sender === "ai" ? (
                <div className="prose prose-invert prose-sm max-w-none">
                  <ReactMarkdown>{msg.text}</ReactMarkdown>
                  
                  {/* Sources List */}
                  {msg.sources && msg.sources.length > 0 && (
                    <div className="mt-4 pt-4 border-t border-slate-700">
                      <p className="text-xs text-slate-400 mb-2 font-semibold">Nguồn tham khảo:</p>
                      <ul className="space-y-1">
                        {msg.sources.map((src, i) => (
                          <li key={i} className="text-xs truncate">
                            <a href={src.url} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:text-blue-300 hover:underline">
                              [{i+1}] {src.source}: {src.title}
                            </a>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ) : (
                <p className="text-sm">{msg.text}</p>
              )}
            </div>
          </div>
        ))}
        
        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-slate-800 rounded-2xl rounded-bl-none p-4 flex gap-2 border border-slate-700">
              <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce"></div>
              <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: "0.2s" }}></div>
              <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: "0.4s" }}></div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
      
      {/* Input Area */}
      <div className="p-4 bg-slate-800 border-t border-slate-700">
        <div className="relative flex items-center">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Hỏi AI về tin tức (Ví dụ: Tình hình kinh tế Việt Nam gần đây ra sao?)..."
            className="w-full bg-slate-900 border border-slate-700 rounded-xl py-3 pl-4 pr-12 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none h-12 flex-grow overflow-hidden"
            rows={1}
          />
          <button 
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            className="absolute right-2 p-2 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:text-slate-500 text-white rounded-lg transition-colors"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4">
              <path d="M3.478 2.404a.75.75 0 0 0-.926.941l2.432 7.905H13.5a.75.75 0 0 1 0 1.5H4.984l-2.432 7.905a.75.75 0 0 0 .926.94 60.519 60.519 0 0 0 18.445-8.986.75.75 0 0 0 0-1.218A60.517 60.517 0 0 0 3.478 2.404Z" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
