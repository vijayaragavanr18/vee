'use client';

import React, { useState, useEffect } from 'react';
import { Header } from '@/components/Header';
import { NewsReader } from '@/components/NewsReader';
import { BottomNav } from '@/components/BottomNav';
import { ArticleModal } from '@/components/ArticleModal';
import { mockArticles } from '@/data/mockArticles';
import { Bookmark, User, Flame, Clock, Award, ChevronRight } from 'lucide-react';

// Premium Cyberpunk AI analysis loading dashboard
const AnalysisLoader = ({
  keyword
}) => {
  const [step, setStep] = useState(0);
  const steps = [`Initializing vector search for "${keyword}"...`, 'Connecting to live global news databases...', 'Extracting key events and timeline insights...', 'Performing multi-perspective sentiment analysis...', 'Stitching interactive 3D news reader interface...'];
  useEffect(() => {
    const interval = setInterval(() => {
      setStep((s) => {
        if (s < steps.length - 1) return s + 1;
        return s;
      });
    }, 350);
    return () => clearInterval(interval);
  }, [steps.length]);
  return <div className="absolute inset-0 bg-background/95 backdrop-blur-md flex flex-col items-center justify-center z-50 p-6">
      <div className="w-full max-w-[420px] bg-surface-container border border-outline-variant/30 rounded-xl p-6 shadow-2xl relative overflow-hidden">
        {/* Top glowing line */}
        <div className="absolute top-0 left-0 w-full h-[2px] bg-gradient-to-r from-transparent via-primary-container to-transparent animate-pulse" />
        
        {/* Pulsing Logo Icon */}
        <div className="w-16 h-16 bg-primary-container/10 border border-primary-container/30 text-primary-container rounded-full mx-auto flex items-center justify-center mb-6 relative">
          <div className="absolute inset-0 rounded-full bg-primary-container/20 animate-ping opacity-75" />
          <svg className="w-8 h-8 animate-pulse" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="9" className="opacity-25" />
            <path d="M12 3v5.5" />
            <path d="M7 8.5l5 7 5-7" />
            <path d="M12 15.5V21" />
          </svg>
        </div>

        <h3 className="text-center font-headline-sm text-headline-sm text-on-surface mb-2 tracking-tight">
          AI Analysis in Progress
        </h3>
        <p className="text-center text-label-sm text-on-surface-variant/60 uppercase tracking-widest mb-6">
          Query: {keyword}
        </p>

        {/* Progress Bar */}
        <div className="w-full h-1 bg-surface-container-highest rounded-full overflow-hidden mb-6">
          <div className="h-full bg-primary-container transition-all duration-300 ease-out" style={{
          width: `${(step + 1) / steps.length * 100}%`
        }} />
        </div>

        {/* Steps Terminal List */}
        <div className="space-y-2.5 font-mono text-[12px] text-left">
          {steps.map((text, idx) => {
          const isCompleted = idx < step;
          const isActive = idx === step;
          return <div key={idx} className={`flex gap-2.5 items-center transition-all duration-200 ${isCompleted ? 'text-emerald-400 opacity-90' : isActive ? 'text-primary-container font-semibold scale-[1.02]' : 'text-on-surface-variant/20'}`}>
                <span className="flex-shrink-0">
                  {isCompleted ? '✓' : isActive ? '●' : '○'}
                </span>
                <span className="truncate">{text}</span>
              </div>;
        })}
        </div>
      </div>
    </div>;
};
export default function Home() {
  const [hasSearched, setHasSearched] = useState(false);
  const [activeTab, setActiveTab] = useState('foryou');
  const [selectedArticle, setSelectedArticle] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [currentArticles, setCurrentArticles] = useState(mockArticles);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [searchKeyword, setSearchKeyword] = useState(null);

  // User interactions state (saved & read lists)
  const [savedIds, setSavedIds] = useState([]);
  const [readIds, setReadIds] = useState([]);
  const [selectedCategory, setSelectedCategory] = useState(null);

  // Hydrate states from localStorage safely
  useEffect(() => {
    const saved = localStorage.getItem('veetrack_saved_ids');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        setTimeout(() => setSavedIds(parsed), 0);
      } catch {

        // Ignored
      }}
    const read = localStorage.getItem('veetrack_read_ids');
    if (read) {
      try {
        const parsed = JSON.parse(read);
        setTimeout(() => setReadIds(parsed), 0);
      } catch {

        // Ignored
      }}
  }, []);
  const saveToStorage = (key, value) => {
    localStorage.setItem(key, JSON.stringify(value));
  };
  const toggleSaveArticle = (articleId) => {
    const updated = savedIds.includes(articleId) ? savedIds.filter((id) => id !== articleId) : [...savedIds, articleId];
    setSavedIds(updated);
    saveToStorage('veetrack_saved_ids', updated);
  };
  const markArticleAsRead = (articleId) => {
    if (!readIds.includes(articleId)) {
      const updated = [...readIds, articleId];
      setReadIds(updated);
      saveToStorage('veetrack_read_ids', updated);
    }
  };
  const handleReadFullStory = (article) => {
    setSelectedArticle(article);
    setIsModalOpen(true);
    markArticleAsRead(article.id);
  };
  const handleCloseModal = () => {
    setIsModalOpen(false);
  };
  const handleTabChange = (tab) => {
    setActiveTab(tab);
    setSelectedCategory(null); // Reset category filter on tab switch
  };
  const handleLogoClick = () => {
    setHasSearched(false);
    setSearchKeyword(null);
  };
  const handleSearch = async (keyword) => {
    setIsAnalyzing(true);
    setSearchKeyword(keyword);
    setActiveTab('foryou'); // Redirect to news reader tab on search
    setSelectedCategory(null);
    try {
      const backendUrl = import.meta.env.VITE_BACKEND_URL || 'http://127.0.0.1:8000';
      const response = await fetch(`${backendUrl}/api/intelligence`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          keywords: [keyword],
          days: 5
        })
      });
      if (response.ok) {
        const data = await response.json();
        const articles = [];
        const CATEGORY_IMAGES = {
          Technology: 'https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=600&q=80',
          Business: 'https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?auto=format&fit=crop&w=600&q=80',
          Science: 'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=600&q=80',
          Culture: 'https://images.unsplash.com/photo-1506157786151-b8491531f063?auto=format&fit=crop&w=600&q=80',
          Sports: 'https://images.unsplash.com/photo-1517649763962-0c623066013b?auto=format&fit=crop&w=600&q=80',
          Global: 'https://images.unsplash.com/photo-1526470608268-f674ce90ebd4?auto=format&fit=crop&w=600&q=80'
        };
        if (data.companyNews && Array.isArray(data.companyNews)) {
          data.companyNews.forEach((item, idx) => {
            const category = item.section === 'company' ? 'Business' : 'Technology';
            const imageUrl = CATEGORY_IMAGES[category] || CATEGORY_IMAGES.Technology;
            
            // Clean up noisy snippets (HTML entities, duplicated suffixes)
            let cleanHeadline = (item.headline || 'Untitled Article').replace(/&nbsp;/gi, ' ').replace(/&amp;/gi, '&').replace(/&quot;/gi, '"');
            let rawSnippet = (item.snippet || '').replace(/&nbsp;/gi, ' ').replace(/&amp;/gi, '&').replace(/&quot;/gi, '"');
            
            // Build extremely elaborate bullets for 'What Happened' and 'Why It Matters'
            let whatHappenedBullets = [];
            let whyItMattersBullets = [];
            
            // Function to split large paragraphs into bullet points
            const textToBullets = (text, fallbackArray) => {
              if (text && text.length > 30) {
                return text.split(/(?<=[.!?])\s+/).filter(s => s.length > 10);
              }
              return fallbackArray;
            };

            // Parse LLM elaborated fields if available
            if (item.llm_what_happened) {
              whatHappenedBullets = textToBullets(item.llm_what_happened, [cleanHeadline, rawSnippet]);
            } else {
              whatHappenedBullets = textToBullets(rawSnippet, [cleanHeadline]);
            }
            
            if (item.llm_why_it_matters) {
              whyItMattersBullets = textToBullets(item.llm_why_it_matters, [item.businessImpact]);
            } else {
              whyItMattersBullets = [item.businessImpact || 'Ongoing monitoring required.', `Sentiment is predominantly ${item.sentiment}.`, `Source authority level: ${item.relevanceScore > 50 ? 'High' : 'Medium'}.`];
            }

            // Construct a highly readable, story-driven AI Narrative
            let storyNarrative = item.llm_ai_narrative;
            if (!storyNarrative || storyNarrative.length < 30) {
                let globalBrief = data.executiveBrief?.happened && data.executiveBrief.happened !== "Analysis unavailable." 
                  ? data.executiveBrief.happened 
                  : '';
                  
                storyNarrative = `This article highlights significant developments regarding ${cleanHeadline}. `;
                if (rawSnippet) {
                  storyNarrative += `Fundamentally, ${rawSnippet.charAt(0).toLowerCase() + rawSnippet.slice(1)} `;
                }
                if (item.businessImpact) {
                  storyNarrative += `From a strategic perspective, ${item.businessImpact.charAt(0).toLowerCase() + item.businessImpact.slice(1)} `;
                }
                storyNarrative += `The overall media sentiment is ${item.sentiment}, suggesting that the audience is perceiving this as ${item.sentiment === 'positive' ? 'highly favorable' : item.sentiment === 'negative' ? 'a potential concern' : 'a neutral matter of fact'}.`;
                
                if (globalBrief) {
                  storyNarrative += `\n\nBroader context: ${globalBrief}`;
                }
            }

            articles.push({
              id: `art-${idx}-${Date.now()}`,
              category: category,
              title: cleanHeadline,
              summary: rawSnippet,
              keywordSummary: `Relevance score: ${item.relevanceScore}/100. Mentioned entities: ${[...(item.entities?.organizations || []), ...(item.entities?.people || [])].join(', ')}.`,
              whatHappened: whatHappenedBullets,
              whyItMatters: whyItMattersBullets,
              aiActions: [item.relevanceExplanation || 'Continue standard tracking.', 'Monitor closely for updates.', 'Cross-reference with related competitors.'],
              imageUrl: imageUrl,
              imageAlt: item.headline,
              author: item.publication,
              publishedAt: item.date || 'Recent',
              readingTime: '3 min read',
              source: item.publication,
              url: item.url,
              sentiment: item.sentiment === 'positive' || item.sentiment === 'negative' ? item.sentiment : 'neutral',
              content: `<p class="mb-4">${item.fullContent || item.snippet}</p>`,
              aiNarrative: storyNarrative
            });
          });
        }
        if (articles.length > 0) {
          setCurrentArticles(articles);
          setHasSearched(true);
        }
      }
    } catch (e) {
      console.error('Search fetch failed:', e);
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Filter logic based on active tab
  const getFilteredArticles = () => {
    if (activeTab === 'saved') {
      return currentArticles.filter((art) => savedIds.includes(art.id));
    }
    if (activeTab === 'explore' && selectedCategory) {
      return currentArticles.filter((art) => art.category.toLowerCase() === selectedCategory.toLowerCase());
    }
    return currentArticles;
  };
  const filteredArticles = getFilteredArticles();
  const categories = Array.from(new Set(currentArticles.map((a) => a.category)));

  // Analytical stats for Profile
  const getFavoriteCategory = () => {
    const readArticles = currentArticles.filter((a) => readIds.includes(a.id));
    if (readArticles.length === 0) return 'None yet';
    const counts = {};
    readArticles.forEach((a) => {
      counts[a.category] = (counts[a.category] || 0) + 1;
    });
    return Object.entries(counts).sort((a, b) => b[1] - a[1])[0][0];
  };

  // Render centered search landing screen
  const renderLandingPage = () => {
    const recommended = ['Quantum Stabilization', 'Vertical Architecture', 'Cybernetic Endurance', 'Tactile Art Exhibition', 'AI Biotechnology'];
    return <div className="w-full max-w-[500px] px-6 flex flex-col justify-center items-center h-full text-center select-none animate-fade-in relative z-10">
        {/* Glowing Background Glow */}
        <div className="absolute top-[20%] left-1/2 -translate-x-1/2 w-72 h-72 bg-primary-container/5 rounded-full blur-[100px] pointer-events-none -z-10 animate-pulse" />

        {/* Vee Track Logo */}
        <div className="w-20 h-20 bg-primary-container/10 border border-primary-container/30 text-primary-container rounded-full flex items-center justify-center mb-6 relative shadow-lg">
          <div className="absolute inset-0 rounded-full bg-primary-container/10 animate-pulse" />
          <svg className="w-10 h-10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="9" className="opacity-25" />
            <path d="M12 3v5.5" />
            <path d="M7 8.5l5 7 5-7" />
            <path d="M12 15.5V21" />
          </svg>
        </div>

        <h1 className="font-headline-lg text-4xl font-extrabold text-on-surface tracking-tight mb-3 select-none">
          VEE <span className="text-primary-container">TRACK</span>
        </h1>

        <p className="text-body-md text-on-surface-variant/80 max-w-[420px] mb-8 leading-relaxed select-none">
          Search any topic to compile, analyze, and generate a customized 3D vertical news digest. Ask AI doubts about any story in real-time.
        </p>

        {/* Large Centered Search Box */}
        <form onSubmit={(e) => {
        e.preventDefault();
        const form = e.currentTarget;
        const input = form.elements.namedItem('searchQuery');
        if (input.value.trim()) {
          handleSearch(input.value.trim());
        }
      }} className="w-full relative flex items-center mb-8">
          <input name="searchQuery" type="text" placeholder="Search topics (e.g. Tesla, SpaceX, Clean Energy)..." required className="w-full bg-surface-container border border-outline-variant/30 hover:border-outline-variant/60 focus:border-primary-container rounded-xl px-4 py-3.5 pr-28 text-on-surface placeholder:text-on-surface-variant/30 focus:outline-none transition-all shadow-xl text-body-md" />
          <button type="submit" className="absolute right-2 px-4 py-2 bg-primary-container text-on-primary-container font-semibold rounded-lg hover:bg-primary-fixed-dim active:scale-95 transition-all cursor-pointer flex items-center justify-center text-label-sm uppercase tracking-wider">
            Generate
          </button>
        </form>

        {/* Suggested Pills */}
        <div className="w-full max-w-[420px]">
          <h4 className="text-[11px] font-semibold text-on-surface-variant/40 tracking-wider uppercase mb-3 select-none">Suggested Topics</h4>
          <div className="flex flex-wrap justify-center gap-2">
            {recommended.map((topic) => <button key={topic} onClick={() => handleSearch(topic)} className="px-3.5 py-1.5 bg-surface-container-low border border-outline-variant/20 hover:border-primary-container/30 hover:bg-surface-container text-on-surface-variant hover:text-primary rounded-full text-label-sm transition-all cursor-pointer">
                {topic}
              </button>)}
          </div>
        </div>
      </div>;
  };

  // Render correct main screen based on active tab selection
  const renderMainContent = () => {
    if (!hasSearched) {
      return renderLandingPage();
    }
    if (activeTab === 'profile') {
      return <div className="w-full max-w-[450px] md:max-w-[600px] h-full flex flex-col justify-start px-6 pt-6 overflow-y-auto pb-6">
          {/* Profile Card */}
          <div className="bg-surface-container border border-outline-variant/30 rounded-lg p-6 mb-6 text-center select-none">
            <div className="w-20 h-20 bg-primary-container/10 border border-primary-container/30 text-primary-container rounded-full mx-auto flex items-center justify-center mb-4">
              <User size={40} />
            </div>
            <h2 className="font-headline-md text-headline-md text-on-surface">Vee Track Reader</h2>
            <p className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-widest mt-1">Premium Reader</p>
          </div>

          {/* Stats Grid */}
          <div className="grid grid-cols-2 gap-4 mb-6">
            <div className="bg-surface-container-low border border-outline-variant/20 rounded-lg p-4 flex flex-col justify-between select-none">
              <div className="flex justify-between items-center text-on-surface-variant mb-2">
                <span className="font-label-sm text-label-sm uppercase tracking-wider">Stories Read</span>
                <Flame size={18} className="text-primary-container" />
              </div>
              <span className="text-3xl font-bold text-on-surface mt-2">{readIds.length}</span>
            </div>

            <div className="bg-surface-container-low border border-outline-variant/20 rounded-lg p-4 flex flex-col justify-between select-none">
              <div className="flex justify-between items-center text-on-surface-variant mb-2">
                <span className="font-label-sm text-label-sm uppercase tracking-wider">Read Time</span>
                <Clock size={18} className="text-primary-container" />
              </div>
              <span className="text-3xl font-bold text-on-surface mt-2">{readIds.length * 4} min</span>
            </div>
          </div>

          {/* Reading Insights Card */}
          <div className="bg-surface-container-lowest border border-outline-variant/20 rounded-lg p-5 select-none">
            <h3 className="font-label-md text-label-md text-primary-container uppercase tracking-widest mb-4">Reading Insights</h3>
            <div className="space-y-4">
              <div className="flex justify-between border-b border-outline-variant/10 pb-2">
                <span className="text-on-surface-variant">Favorite Topic</span>
                <span className="text-on-surface font-semibold">{getFavoriteCategory()}</span>
              </div>
              <div className="flex justify-between border-b border-outline-variant/10 pb-2">
                <span className="text-on-surface-variant">Saved Stories</span>
                <span className="text-on-surface font-semibold">{savedIds.length}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-on-surface-variant">Access level</span>
                <span className="text-primary-container font-semibold flex items-center gap-1">
                  <Award size={16} /> Premium
                </span>
              </div>
            </div>
          </div>
        </div>;
    }
    if (activeTab === 'explore') {
      if (selectedCategory) {
        return <div className="w-full h-full flex flex-col items-center">
            {/* Category header */}
            <div className="w-full max-w-[450px] sm:max-w-[540px] md:max-w-[620px] lg:max-w-[680px] px-container-padding py-3 flex justify-between items-center border-b border-outline-variant/10 bg-background/50 backdrop-blur-sm z-10">
              <span className="text-label-md font-semibold text-primary-container uppercase tracking-widest">
                Category: {selectedCategory}
              </span>
              <button onClick={() => setSelectedCategory(null)} className="text-label-sm text-on-surface-variant hover:text-primary cursor-pointer select-none underline">
                Back to Topics
              </button>
            </div>
            <div className="flex-1 w-full relative overflow-hidden">
              <NewsReader key={selectedCategory || 'explore'} articles={filteredArticles} onReadFullStory={handleReadFullStory} />
            </div>
          </div>;
      }
      return <div className="w-full max-w-[450px] md:max-w-[600px] h-full flex flex-col justify-start px-6 pt-6 overflow-y-auto pb-6">
          <div className="mb-6 select-none">
            <h2 className="font-headline-md text-headline-md text-on-surface mb-2">Explore Topics</h2>
            <p className="text-on-surface-variant">Select a topic to focus your news cards</p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {categories.map((cat) => {
            const count = currentArticles.filter((a) => a.category === cat).length;
            return <button key={cat} onClick={() => setSelectedCategory(cat)} className="bg-surface-container border border-outline-variant/30 hover:border-primary-container/50 rounded-lg p-5 text-left transition-all duration-300 group cursor-pointer">
                  <div className="flex justify-between items-start">
                    <span className="inline-block px-2.5 py-0.5 bg-primary-container/10 border border-primary-container/20 text-primary-container rounded-full text-label-sm uppercase tracking-wider mb-3">
                      Topic
                    </span>
                    <ChevronRight size={18} className="text-on-surface-variant/40 group-hover:text-primary-container group-hover:translate-x-1 transition-all" />
                  </div>
                  <h3 className="font-headline-sm text-headline-sm text-on-surface group-hover:text-primary-container transition-colors">
                    {cat}
                  </h3>
                  <p className="text-label-sm text-on-surface-variant mt-2">
                    {count} {count === 1 ? 'article' : 'articles'}
                  </p>
                </button>;
          })}
          </div>
        </div>;
    }
    if (activeTab === 'saved' && filteredArticles.length === 0) {
      return <div className="w-full max-w-[450px] h-full flex flex-col items-center justify-center px-8 text-center select-none">
          <div className="w-16 h-16 bg-surface-container border border-outline-variant/20 rounded-full flex items-center justify-center text-on-surface-variant/40 mb-4">
            <Bookmark size={28} />
          </div>
          <h2 className="font-headline-sm text-headline-sm text-on-surface mb-2">No Saved Stories</h2>
          <p className="text-on-surface-variant text-body-md leading-relaxed">
            Click the bookmark icon inside any article details page to save it for easy offline reading.
          </p>
          <button onClick={() => setActiveTab('foryou')} className="mt-6 px-6 py-2 bg-primary-container text-on-primary-container font-semibold rounded hover:bg-primary-fixed-dim active:scale-95 transition-all cursor-pointer uppercase tracking-wider text-label-sm">
            Go to Reader
          </button>
        </div>;
    }
    return <NewsReader key={searchKeyword || 'default'} articles={filteredArticles} onReadFullStory={handleReadFullStory} />;
  };
  return <div className="flex flex-col h-screen overflow-hidden select-none bg-background text-on-surface antialiased animate-fade-in">
      {/* Top Header Bar */}
      <Header activeTab={hasSearched ? activeTab : undefined} onTabChange={handleTabChange} onSearch={handleSearch} onLogoClick={handleLogoClick} hideNav={!hasSearched} visible={true} />

      {/* Main Content Viewport */}
      <main className="flex-1 w-full flex justify-center pt-16 pb-[72px] md:pb-0 relative overflow-hidden">
        {isAnalyzing && searchKeyword && <AnalysisLoader keyword={searchKeyword} />}
        {renderMainContent()}
      </main>

      {/* Bottom Nav Bar (Mobile Viewports Only) */}
      {hasSearched && <BottomNav activeTab={activeTab} onTabChange={handleTabChange} />}

      {/* Full Article Overlay Modal */}
      <ArticleModal article={selectedArticle} isOpen={isModalOpen} onClose={handleCloseModal} isSaved={selectedArticle ? savedIds.includes(selectedArticle.id) : false} onToggleSave={toggleSaveArticle} />
    </div>;
}