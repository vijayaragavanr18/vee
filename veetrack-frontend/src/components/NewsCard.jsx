'use client';

import React, { useState, useEffect, useRef } from 'react';
import { ExternalLink, ChevronRight, MessageSquare, Send, X, Loader2 } from 'lucide-react';
export const NewsCard = ({
  article,
  stateClass,
  onReadFullStory,
  activePageIndex = 0,
  onPageChange,
  dragOffset = 0,
  isDragging = false
}) => {
  // Q&A Chatbot state
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [chatInput, setChatInput] = useState('');
  const [chatMessages, setChatMessages] = useState([]);
  const [isChatLoading, setIsChatLoading] = useState(false);
  const chatScrollRef = useRef(null);

  // Auto-scroll chat to bottom
  useEffect(() => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight;
    }
  }, [chatMessages, isChatOpen]);
  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!chatInput.trim() || isChatLoading) return;
    const userText = chatInput.trim();
    setChatInput('');
    const updatedMessages = [...chatMessages, {
      role: 'user',
      text: userText
    }];
    setChatMessages(updatedMessages);
    setIsChatLoading(true);
    try {
      const backendUrl = import.meta.env.VITE_BACKEND_URL || 'http://127.0.0.1:8000';
      const startResp = await fetch(`${backendUrl}/api/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          article_title: article.title,
          article_text: article.content,
          article_url: ""
        })
      });
      if (!startResp.ok) throw new Error('Failed to start chat session');
      const {
        session_id
      } = await startResp.json();
      const fullQuestion = chatMessages && chatMessages.length > 0 ? `Previous Context:\n${chatMessages.map((h) => `${h.role}: ${h.text}`).join('\n')}\n\nNew Question: ${userText}` : userText;
      const askResp = await fetch(`${backendUrl}/api/chat/ask`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          session_id: session_id,
          question: fullQuestion
        })
      });
      if (askResp.ok) {
        const data = await askResp.json();
        if (data.answer) {
          setChatMessages([...updatedMessages, {
            role: 'assistant',
            text: data.answer
          }]);
        }
      } else {
        setChatMessages([...updatedMessages, {
          role: 'assistant',
          text: "Sorry, I couldn't reach the server. Please try again."
        }]);
      }
      fetch(`${backendUrl}/api/chat?session_id=${session_id}`, {
        method: 'DELETE'
      }).catch(() => {});
    } catch (error) {
      console.error('Chat error:', error);
      setChatMessages([...updatedMessages, {
        role: 'assistant',
        text: 'An error occurred while answering your question.'
      }]);
    } finally {
      setIsChatLoading(false);
    }
  };

  // Renders the full article design.
  // This is duplicated in the top and bottom halves to create the split fold illusion.
  const renderCardContent = (isTop) => <article className="card-content-full bg-surface border border-outline-variant/30 md:border-outline-variant select-none">
      {/* Article Image (Top 45% of height when visible) */}
      <div className={`w-full relative shrink-0 bg-surface-container-lowest overflow-hidden transition-all duration-500 ease-in-out ${activePageIndex === 0 ? 'h-[45%] opacity-100' : 'h-0 opacity-0 pointer-events-none'}`}>
        <img src={article.imageUrl} alt={article.imageAlt} className="w-full h-full object-cover grayscale opacity-90 mix-blend-luminosity" draggable="false" />
        <div className="absolute inset-0 bg-gradient-to-t from-surface to-transparent" />

        {/* Source and Sentiment Badges */}
        <div className="absolute top-4 left-4 right-4 flex justify-between items-center z-20">
          <span className="px-2.5 py-0.5 bg-background/80 backdrop-blur-md border border-outline-variant/30 text-on-surface rounded-full font-label-sm text-[11px] uppercase tracking-wider shadow-sm">
            {article.source}
          </span>
          <span className={`px-2.5 py-0.5 rounded-full font-label-sm text-[11px] uppercase tracking-wider shadow-sm flex items-center gap-1.5 bg-background/80 backdrop-blur-md border ${article.sentiment === 'positive' ? 'border-emerald-500/30 text-emerald-400' : article.sentiment === 'negative' ? 'border-rose-500/30 text-rose-400' : 'border-yellow-500/30 text-yellow-400'}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${article.sentiment === 'positive' ? 'bg-emerald-500' : article.sentiment === 'negative' ? 'bg-rose-500' : 'bg-yellow-500'}`} />
            {article.sentiment}
          </span>
        </div>
      </div>

      {/* Article Text Details (Bottom 55% of height on page 1, 100% on pages 2-4) */}
      <div className="flex-1 overflow-hidden relative flex flex-col pt-1 pb-8">
        <div className="flex-1 flex flex-row w-[400%]" style={{
        transform: `translateX(calc(-${activePageIndex * 25}% + ${dragOffset}px))`,
        transition: isDragging ? 'none' : 'transform 500ms cubic-bezier(0.25, 1, 0.5, 1)'
      }}>
          {/* Page 1: Summary */}
          <div className="w-1/4 h-full px-container-padding pt-3 pb-12 flex flex-col justify-between shrink-0 box-border">
            <div>
              <div className="flex justify-between items-center mb-2">
                <span className="inline-block px-2.5 py-0.5 border border-primary-container/30 text-primary-container rounded-full font-label-sm text-[11px] uppercase tracking-wider">
                  {article.category}
                </span>
                <span className="text-[11px] font-mono text-on-surface-variant/50">1/4 • OVERVIEW</span>
              </div>
              <h2 className="font-headline-lg text-headline-md sm:text-headline-lg-mobile md:text-headline-lg text-on-surface mb-3 line-clamp-2 leading-tight">
                {article.title}
              </h2>
              <p className="font-body-lg text-body-md md:text-body-lg text-on-surface-variant line-clamp-3 md:line-clamp-4 leading-relaxed text-justify">
                {article.keywordSummary || article.summary}
              </p>
            </div>

            <div className="pt-2 flex justify-between items-center">
              <button onClick={!isTop ? (e) => {
              e.preventDefault();
              e.stopPropagation();
              if (article.url) {
                window.open(article.url, '_blank', 'noopener,noreferrer');
              } else {
                onReadFullStory(article);
              }
            } : undefined} onMouseDown={(e) => e.stopPropagation()} onTouchStart={(e) => e.stopPropagation()} tabIndex={isTop ? -1 : 0} disabled={isTop} className={`inline-flex items-center gap-1.5 text-blue-400 font-label-md text-[12px] font-semibold tracking-wide uppercase transition-colors ${isTop ? 'pointer-events-none opacity-50' : 'hover:text-blue-300 cursor-pointer'}`}>
                Read Original Story
                <ExternalLink size={14} className="opacity-80" />
              </button>
              <span className="text-[11px] text-on-surface-variant/40 flex items-center gap-1">Swipe left <ChevronRight size={10} /></span>
            </div>
          </div>

          {/* Page 2: What Happened & Why It Happened */}
          <div className="w-1/4 h-full px-container-padding pt-3 pb-12 flex flex-col justify-between shrink-0 box-border">
            <div className="flex flex-col flex-1 overflow-hidden">
              <div className="flex justify-between items-center mb-3 shrink-0">
                <span className="inline-block px-2.5 py-0.5 bg-blue-500/10 border border-blue-500/30 text-blue-400 rounded-full font-label-sm text-[11px] uppercase tracking-wider">
                  Facts & Analysis
                </span>
                <span className="text-[11px] font-mono text-on-surface-variant/50">2/4 • THE FACTS</span>
              </div>
              <div className="flex-1 overflow-y-auto space-y-4 pr-1 scrollbar-thin">
                <div>
                  <h4 className="text-[10px] font-bold text-blue-400 uppercase tracking-wider mb-2">What Happened</h4>
                  <ul className="space-y-2 font-body-lg text-body-md md:text-body-lg text-on-surface-variant leading-relaxed">
                    {article.whatHappened?.map((point, index) => <li key={index} className="flex gap-2 items-start text-left">
                        <span className="text-blue-400 mt-2 shrink-0 w-1.5 h-1.5 rounded-full bg-blue-400" />
                        <span>{point}</span>
                      </li>) || <li className="text-on-surface-variant/40 italic">No details available.</li>}
                  </ul>
                </div>
                <div>
                  <h4 className="text-[10px] font-bold text-amber-400 uppercase tracking-wider mb-2 mt-2">Why It Happened</h4>
                  <ul className="space-y-2 font-body-lg text-body-md md:text-body-lg text-on-surface-variant leading-relaxed">
                    {article.whyItMatters?.map((point, index) => <li key={index} className="flex gap-2 items-start text-left">
                        <span className="text-amber-400 mt-2 shrink-0 w-1.5 h-1.5 rounded-full bg-amber-400" />
                        <span>{point}</span>
                      </li>) || <li className="text-on-surface-variant/40 italic">No details available.</li>}
                  </ul>
                </div>
              </div>
            </div>
            <div className="pt-2 flex justify-between items-center text-[11px] text-on-surface-variant/40 shrink-0">
              <span>Swipe right to go back</span>
              <span className="flex items-center gap-1">Swipe left <ChevronRight size={10} /></span>
            </div>
          </div>

          {/* Page 3: AI Narrative */}
          <div className="w-1/4 h-full px-container-padding pt-3 pb-12 flex flex-col justify-between shrink-0 box-border">
            <div className="flex flex-col flex-1 overflow-hidden">
              <div className="flex justify-between items-center mb-3 shrink-0">
                <span className="inline-block px-2.5 py-0.5 bg-purple-500/10 border border-purple-500/30 text-purple-400 rounded-full font-label-sm text-[11px] uppercase tracking-wider">
                  AI Narrative
                </span>
                <span className="text-[11px] font-mono text-on-surface-variant/50">3/4 • COGNITIVE POV</span>
              </div>
              <div className="flex-1 overflow-y-auto pr-1 scrollbar-thin">
                <p className="font-body-lg text-body-md md:text-body-lg text-on-surface-variant leading-relaxed text-justify whitespace-pre-line italic pr-1">
                  &ldquo;{article.aiNarrative}&rdquo;
                </p>
              </div>
            </div>
            <div className="pt-2 flex justify-between items-center text-[11px] text-on-surface-variant/40 shrink-0">
              <span>Swipe right</span>
              <span className="flex items-center gap-1">Swipe left <ChevronRight size={10} /></span>
            </div>
          </div>

          {/* Page 4: Suggested Actions */}
          <div className="w-1/4 h-full px-container-padding pt-3 pb-12 flex flex-col justify-between shrink-0 box-border">
            <div className="flex flex-col flex-1 overflow-hidden">
              <div className="flex justify-between items-center mb-3 shrink-0">
                <span className="inline-block px-2.5 py-0.5 bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 rounded-full font-label-sm text-[11px] uppercase tracking-wider">
                  Suggested Actions
                </span>
                <span className="text-[11px] font-mono text-on-surface-variant/50">4/4 • ACTION PLAYBOOK</span>
              </div>
              <div className="flex-1 overflow-y-auto pr-1 scrollbar-thin">
                <ul className="space-y-3 font-body-lg text-body-md md:text-body-lg text-on-surface-variant leading-relaxed">
                  {article.aiActions?.map((point, index) => <li key={index} className="flex gap-2 items-start text-left">
                      <span className="text-emerald-400 mt-2 shrink-0 w-1.5 h-1.5 rounded-full bg-emerald-400" />
                      <span>{point}</span>
                    </li>) || <li className="text-on-surface-variant/40 italic">No details available.</li>}
                </ul>
              </div>
            </div>
            <div className="pt-2 flex justify-between items-center text-[11px] text-on-surface-variant/40 shrink-0">
              <span>Swipe right</span>
              <span className="text-emerald-400 font-semibold flex items-center gap-0.5">Ready <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping" /></span>
            </div>
          </div>
        </div>

        {/* Compact Q&A Bot Trigger Input */}
        <div className={`absolute bottom-8 left-container-padding right-container-padding z-30 select-none ${isTop ? 'pointer-events-none' : ''}`}>
          <div onClick={!isTop ? (e) => {
          e.preventDefault();
          e.stopPropagation();
          setIsChatOpen(true);
        } : undefined} onMouseDown={(e) => e.stopPropagation()} onTouchStart={(e) => e.stopPropagation()} tabIndex={isTop ? -1 : 0} className={`flex items-center gap-2 px-3 py-1.5 bg-surface-container-high border border-outline-variant/30 hover:border-primary-container/40 rounded-lg text-on-surface-variant/50 text-[10px] transition-all ${isTop ? '' : 'cursor-pointer'}`}>
            <MessageSquare size={12} className="text-primary-container" />
            <span className="flex-1 text-left">Ask AI about this story...</span>
            <span className="text-[9px] px-1.5 py-0.5 bg-primary-container/10 border border-primary-container/20 text-primary-container rounded uppercase font-mono">Ask Bot</span>
          </div>
        </div>

        {/* Card Sub-page Indicator Dots */}
        <div className="absolute bottom-2.5 left-0 right-0 flex justify-center gap-1.5 z-20 select-none">
          {[0, 1, 2, 3].map((idx) => <button key={idx} onClick={!isTop ? (e) => {
          e.preventDefault();
          e.stopPropagation();
          if (onPageChange) onPageChange(idx);
        } : undefined} onMouseDown={(e) => e.stopPropagation()} onTouchStart={(e) => e.stopPropagation()} tabIndex={isTop ? -1 : 0} disabled={isTop} className={`w-1.5 h-1.5 rounded-full transition-all duration-300 ${isTop ? 'pointer-events-none' : 'cursor-pointer'} ${idx === activePageIndex ? 'bg-primary-container w-3.5' : 'bg-on-surface-variant/20 hover:bg-on-surface-variant/40'}`} aria-label={`Go to sub-page ${idx + 1}`} />)}
        </div>

        {/* Q&A Chat Drawer Overlay */}
        <div onClick={(e) => {
        e.stopPropagation();
      }} onMouseDown={(e) => {
        e.stopPropagation();
      }} onMouseUp={(e) => {
        e.stopPropagation();
      }} onMouseMove={(e) => {
        e.stopPropagation();
      }} onTouchStart={(e) => {
        e.stopPropagation();
      }} onTouchMove={(e) => {
        e.stopPropagation();
      }} onTouchEnd={(e) => {
        e.stopPropagation();
      }} onWheel={(e) => {
        e.stopPropagation();
      }} className={`absolute inset-0 bg-surface-container-lowest border-t border-outline-variant/30 flex flex-col z-40 transition-transform duration-300 ease-out select-none ${isChatOpen ? 'translate-y-0' : 'translate-y-full'}`}>
          {/* Chat Header */}
          <div className="h-10 border-b border-outline-variant/20 px-container-padding flex justify-between items-center bg-surface-container-low shrink-0 select-none">
            <span className="text-[11px] font-semibold text-primary-container tracking-wider uppercase flex items-center gap-1.5">
              <MessageSquare size={12} />
              AI Assistant
            </span>
            <button onClick={isTop ? (e) => {
            e.preventDefault();
            e.stopPropagation();
            setIsChatOpen(false);
          } : undefined} tabIndex={isTop ? 0 : -1} disabled={!isTop} className={`text-on-surface-variant/60 hover:text-primary p-1 rounded-full transition-colors ${isTop ? 'cursor-pointer hover:bg-surface-container-high' : 'pointer-events-none opacity-40'}`} aria-label="Close Chat">
              <X size={14} />
            </button>
          </div>

          {/* Chat Messages */}
          <div ref={chatScrollRef} className="flex-1 overflow-y-auto p-4 space-y-3 scrollbar-thin select-text flex flex-col">
            <div className="max-w-[85%] self-start bg-surface-container-high text-on-surface-variant rounded-xl rounded-tl-none px-3.5 py-2 text-[11px] leading-relaxed mr-auto select-text">
              Hi! Ask me any questions or doubts about &ldquo;{article.title}&rdquo;. I&apos;m here to clarify!
            </div>

            {chatMessages.map((msg, idx) => <div key={idx} className={`max-w-[85%] rounded-xl px-3.5 py-2 text-[11px] leading-relaxed select-text ${msg.role === 'user' ? 'self-end bg-primary-container/10 border border-primary-container/30 text-on-surface rounded-tr-none ml-auto' : 'self-start bg-surface-container-high text-on-surface-variant rounded-tl-none mr-auto'}`}>
                {msg.text}
              </div>)}

            {isChatLoading && <div className="max-w-[85%] self-start bg-surface-container-high text-on-surface-variant/40 rounded-xl rounded-tl-none px-3.5 py-2 text-[11px] flex items-center gap-1.5 mr-auto animate-pulse select-none">
                <Loader2 size={12} className="animate-spin text-primary-container" />
                Thinking...
              </div>}
          </div>

          {/* Chat Input Form */}
          <form onSubmit={!isTop ? handleSendMessage : (e) => e.preventDefault()} className="p-2 border-t border-outline-variant/20 bg-surface-container-low flex items-center gap-2 shrink-0 select-none">
            <input type="text" placeholder="Ask a question..." value={chatInput} onChange={!isTop ? (e) => setChatInput(e.target.value) : undefined} onKeyDown={(e) => {
            e.stopPropagation(); // Stop arrow navigation while typing!
          }} tabIndex={isTop ? -1 : 0} readOnly={isTop} className="flex-1 bg-surface-container-highest border border-outline-variant/30 focus:border-primary-container rounded-lg px-3 py-1.5 text-[11px] text-on-surface placeholder:text-on-surface-variant/30 focus:outline-none transition-all" />
            <button type="submit" disabled={isTop || !chatInput.trim() || isChatLoading} tabIndex={isTop ? -1 : 0} className={`p-1.5 bg-primary-container text-on-primary-container rounded-lg transition-all flex items-center justify-center shrink-0 ${isTop ? 'pointer-events-none opacity-40' : 'hover:bg-primary-fixed-dim cursor-pointer'}`} aria-label="Send Message">
              <Send size={12} />
            </button>
          </form>
        </div>
      </div>
    </article>;
  return <div className={`news-card-wrapper ${stateClass}`} data-index={article.id}>
      {/* Top half folds downwards / upwards */}
      <div className="card-half card-top">
        {renderCardContent(true)}
      </div>

      {/* Bottom half folds upwards / downwards */}
      <div className="card-half card-bottom">
        {renderCardContent(false)}
      </div>
    </div>;
};