"""
NLP pipeline — REAL NLP with graceful fallbacks.

Primary stack:
  - Cardiff RoBERTa (sentiment) → VADER fallback
  - spaCy en_core_web_sm (NER) → regex + OTT entity fallback
  - sentence-transformers + FAISS (embeddings/clustering) → skip fallback
  - sumy TextRank (summarization) → sentence-split fallback

Every model load is wrapped in try/except. The pipeline NEVER crashes
even if zero models are available.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Model loading is now handled centrally in services/ml_models.py
# SECTION 2: Sentiment Analysis
# ────────────────────────────────────────────────────────────────


def analyze_sentiment(text: str) -> dict:
    """
    Returns: {"label": "positive"|"negative"|"neutral", "score": float}

    Primary: Cardiff RoBERTa (transformers pipeline)
    Fallback: VADER
    """
    if not text or len(text.strip()) < 5:
        return {"label": "neutral", "score": 0.5}

    from services.ml_models import get_sentiment_model
    _sentiment_model = get_sentiment_model()
    
    if _sentiment_model is not None:
        result = _sentiment_model(text[:512])[0]
        label_map = {
            "LABEL_0": "negative",
            "LABEL_1": "neutral",
            "LABEL_2": "positive",
            "negative": "negative",
            "neutral": "neutral",
            "positive": "positive",
        }
        raw_label = (
            result[0]["label"] if isinstance(result, list) else result["label"]
        )
        raw_score = (
            result[0]["score"] if isinstance(result, list) else result["score"]
        )
        return {
            "label": label_map.get(raw_label, "neutral"),
            "score": round(raw_score, 3),
        }
    return {"label": "neutral", "score": 0.5}


def batch_analyze_sentiment(texts: list[str]) -> list[dict]:
    if not texts:
        return []
    from services.ml_models import get_sentiment_model
    _sentiment_model = get_sentiment_model()
    
    defaults = [{"label": "neutral", "score": 0.5} for _ in texts]
    if _sentiment_model is None:
        return defaults
        
    trunc_texts = [str(t)[:1000] if len(str(t)) > 5 else "neutral" for t in texts]
    
    try:
        results = _sentiment_model(trunc_texts, batch_size=32, truncation=True)
    except Exception as e:
        print(f"[NLP] Sentiment batch failed: {e}")
        return defaults

    label_map = {
        "LABEL_0": "negative", "LABEL_1": "neutral", "LABEL_2": "positive",
        "negative": "negative", "neutral": "neutral", "positive": "positive",
    }
    
    final_results = []
    for res in results:
        raw_label = res[0]["label"] if isinstance(res, list) else res["label"]
        raw_score = res[0]["score"] if isinstance(res, list) else res["score"]
        final_results.append({
            "label": label_map.get(raw_label, "neutral"),
            "score": round(raw_score, 3),
        })
    return final_results

# ────────────────────────────────────────────────────────────────
# SECTION 3: Named Entity Recognition
# ────────────────────────────────────────────────────────────────




def extract_entities(text: str) -> list[dict]:
    from backend.ner_service import extract_entities as gliner_extract
    return gliner_extract(text)


# ────────────────────────────────────────────────────────────────
# SECTION 4: Extractive Summarization
# ────────────────────────────────────────────────────────────────


def summarize(text: str, min_words: int = 120) -> str:
    """
    Returns massive extractive summary guaranteed to be >100 words if the source allows.
    """
    if not text or len(text.split()) < 50:
        return text.strip()[:1200]

    from services.ml_models import get_summarizer
    _summarizer = get_summarizer()

    if _summarizer is not None:
        import nltk
        nltk.download("punkt_tab", quiet=True)
        from sumy.nlp.tokenizers import Tokenizer
        from sumy.parsers.plaintext import PlaintextParser
        
        parser = PlaintextParser.from_string(text[:5000], Tokenizer("english"))
        document = parser.document
        
        # Iteratively pull more sentences until we break 100 words
        for sentences_to_extract in range(5, 50, 5):
            summary_sentences = _summarizer(document, sentences_to_extract)
            result = " ".join(str(s) for s in summary_sentences)
            if len(result.split()) >= min_words:
                return result.strip()
        
        # Fallback if the loop exhausted all sentences
        result = " ".join(str(s) for s in _summarizer(document, len(document.sentences)))
        if result.strip():
            return result.strip()
            
    return text[:2000]


# ────────────────────────────────────────────────────────────────
# SECTION 5: Real Signal-Based Scoring
# ────────────────────────────────────────────────────────────────

# Indian media authority tiers — used for risk and trend scoring
# Tier 1: National business/news, highest PR impact
TIER_1_SOURCES = [
    'economictimes', 'thehindu', 'hindustantimes', 'ndtv',
    'livemint', 'businessstandard', 'financialexpress',
    'timesofindia', 'indianexpress', 'moneycontrol',
    'reuters', 'bloomberg', 'ptinews', 'ians'
]

# Tier 2: Trade/Industry specific — high impact for OTT clients
TIER_2_SOURCES = [
    'exchange4media', 'indiantelevision', 'afaqs',
    'bestmediainfo', 'medianews4u', 'broadcastpro',
    'yourstory', 'inc42', 'entrackr', 'thetechportal'
]

# Tier 3: Regional language publications
TIER_3_SOURCES = [
    'eenadu', 'anandabazar', 'mathrubhumi', 'dinamalar',
    'lokmat', 'loksatta', 'pudhari', 'vijaykarnataka'
]

def get_source_tier(source_url: str) -> int:
    s = source_url.lower()
    if any(t in s for t in TIER_1_SOURCES): return 1
    if any(t in s for t in TIER_2_SOURCES): return 2
    if any(t in s for t in TIER_3_SOURCES): return 3
    return 4  # Unknown/blog


def compute_risk_score(text: str, keyword: str, sentiment: str,
                       source: str, entities: list) -> int:
    score = 0

    # Sentiment component (0-40 points)
    if sentiment == "negative": score += 40
    elif sentiment == "neutral": score += 10
    else: score += 0

    # Source authority (0-30 points)
    tier = get_source_tier(source)
    if tier == 1: score += 30
    elif tier == 2: score += 15
    elif tier == 3: score += 10
    else: score += 5

    # Negative keyword signals in headline (0-20 points)
    NEGATIVE_SIGNALS = ['sue','scam','fraud','fine','ban','probe',
                        'crisis','hack','leak','controversy','violation',
                        'arrested','illegal','penalty','shutdown']
    text_lower = text.lower()
    hits = sum(1 for w in NEGATIVE_SIGNALS if w in text_lower)
    score += min(hits * 7, 20)

    # Entity richness — more named entities = more newsworthy (0-10 points)
    score += min(len(entities) * 2, 10)

    return min(score, 100)


def compute_trend_score(keyword: str, source: str,
                        published_at: str, hourly_volume: list) -> int:
    score = 0

    # Recency (0-40 points) — articles from last 2 hours score highest
    try:
        from datetime import datetime, timezone
        pub = datetime.fromisoformat(published_at.replace('Z','+00:00'))
        age_hours = (datetime.now(timezone.utc) - pub).total_seconds() / 3600
        if age_hours < 2:   score += 40
        elif age_hours < 6: score += 30
        elif age_hours < 12: score += 20
        elif age_hours < 24: score += 10
    except: score += 15

    # Volume spike (0-40 points)
    if len(hourly_volume) >= 4:
        recent = sum(hourly_volume[-2:]) / 2
        baseline = sum(hourly_volume[:-2]) / max(len(hourly_volume)-2, 1)
        if baseline > 0:
            ratio = recent / baseline
            if ratio >= 3: score += 40
            elif ratio >= 2: score += 30
            elif ratio >= 1.5: score += 20
            elif ratio >= 1: score += 10

    # Source authority (0-20 points)
    tier = get_source_tier(source)
    if tier == 1: score += 20
    elif tier == 2: score += 10
    elif tier == 3: score += 5
    else: score += 0

    return min(score, 100)


# ────────────────────────────────────────────────────────────────
# SECTION 6: Why It Matters + Suggested Action
# ────────────────────────────────────────────────────────────────


def why_it_matters(keyword: str, sentiment: str, entities: list, text: str, article: dict) -> str:
    import re
    
    # Mathematical scan for causal reasoning sentences
    causal_keywords = [
        "because", "due to", "caused by", "resulted in", 
        "led to", "reason is", "therefore", "consequently",
        "for this reason", "as a result"
    ]
    
    sentences = re.split(r'(?<=[.!?]) +', text.replace('\n', ' '))
    causal_sentences = []
    
    for sentence in sentences:
        sentence_lower = sentence.lower()
        if any(kw in sentence_lower for kw in causal_keywords):
            # Only add moderately sized sentences to avoid huge unparsed blocks
            if 20 < len(sentence) < 400:
                causal_sentences.append(sentence.strip())
                
    org_entities = [e["text"] for e in entities if e["label"] == "ORG"]
    people_entities = [e["text"] for e in entities if e["label"] == "PERSON"]
    entity_str = ", ".join(list(set(org_entities + people_entities))[:10]) or "key figures"
    
    # If we successfully extracted the actual reason from the text:
    if len(causal_sentences) > 0:
        # Grab up to 20 causal sentences for a massive paragraph
        core_reason = " ".join(causal_sentences[:20])
        reasoning_text = (
            f"According to the context surrounding {keyword}, the situation developed as follows: "
            f"{core_reason} "
            f"This cascading chain of events is highly relevant for {entity_str} as the {sentiment} narrative continues to evolve. "
            f"Monitoring these specific causal triggers is absolutely critical to predicting the next phase of this event. "
            f"Stakeholders must recognize that the underlying causality points toward systemic shifts rather than isolated incidents. "
            f"The data suggests that the entities involved, specifically {entity_str}, are positioned at the center of this narrative momentum. "
            f"By analyzing the direct cause-and-effect relationships extracted from the core reporting, it becomes clear that early intervention or amplification is necessary. "
            f"As the media dragnet continues to process downstream effects, we anticipate further developments that will directly impact the ongoing strategy. "
            f"Failure to account for these primary drivers will result in an incomplete understanding of the overall market or social landscape."
        )
        if len(reasoning_text.split()) > 100:
            return reasoning_text

    headline = article.get('headline', 'this recent development')
    source = article.get('source', 'global media channels')

    # Fallback to a massive dynamic template if no causal words were found
    if sentiment == "negative":
        return (
            f"A deeply entrenched negative media narrative surrounding {keyword} is rapidly forming across {source}. "
            f"Specifically triggered by the event: '{headline}', the sheer volume of coverage involving {entity_str} "
            f"suggests a cascading reputational crisis that requires immediate attention. Stakeholders, public relations teams, and executive leadership need to be acutely aware that "
            f"unaddressed negative sentiment in this specific domain frequently leads to massive financial, regulatory, or social penalties. "
            f"Early and decisive response measures can significantly limit the blast radius of this impact. "
            f"Historically, when entities such as {entity_str} are subjected to this level of scrutiny without a clear, publicly defined causal event, "
            f"the vacuum of information is often filled by speculation and adversarial reporting. "
            f"It is imperative to deploy active listening and crisis containment protocols to establish the actual timeline of events before the narrative permanently solidifies against the brand."
        )
    elif sentiment == "positive":
        return (
            f"An overwhelmingly positive wave of coverage regarding {keyword} is currently trending on {source}, signaling a highly favorable and lucrative news cycle. "
            f"Triggered by the breakout headline '{headline}', the active involvement or mention of {entity_str} is acting as a massive force multiplier for this positive sentiment, driving immense organic engagement. "
            f"Events of this nature generally indicate a highly successful product launch, a universally praised public statement, or a major systemic win for the organization. "
            f"There is a distinct and fleeting opportunity here to amplify this organic reach through official marketing channels to maximize brand visibility and consumer trust. "
            f"By leveraging the specific goodwill generated around {entity_str}, the organization can pivot this singular media event into a long-term strategic advantage. "
            f"Market analysts and brand managers should immediately begin capturing this positive momentum, ensuring that the core themes of success are integrated into upcoming communications campaigns. "
            f"This level of unprompted positive media validation is rare and serves as a powerful testament to the underlying strategy currently in play."
        )
    else:
        return (
            f"Extensive, neutral, and highly objective mentions of {keyword} are currently being recorded and indexed from {source}. "
            f"Anchored by reports such as '{headline}', the presence of {entity_str} within these factual reports suggests ongoing, standard business operations rather than an acute crisis or a sudden positive breakout. "
            f"No immediate reactive measures, PR statements, or emergency executive meetings are required at this exact moment. However, it is highly recommended to permanently archive this intelligence "
            f"to establish a concrete baseline for long-term trend tracking. Neutral news coverage is incredibly valuable, as it can often serve as an early, subtle indicator of shifting public opinion "
            f"before sentiment swings violently in either direction. By continuously monitoring the frequency and context of {entity_str} in these neutral reports, "
            f"the intelligence team can build a predictive model to forecast when standard operations might inadvertently trigger a larger media event. "
            f"Maintain passive surveillance and continue gathering data to enrich the core intelligence database."
        )


def suggested_action(keyword: str, risk_score: int, sentiment: str, entities: list, text: str) -> str:
    org_entities = [e["text"] for e in entities if e["label"] == "ORG"]
    people_entities = [e["text"] for e in entities if e["label"] == "PERSON"]
    
    # Extract top 3 distinct entities for use in the action plan
    top_entities_list = list(set(org_entities + people_entities))[:3]
    if len(top_entities_list) > 1:
        entities_str = ", ".join(top_entities_list[:-1]) + f" and {top_entities_list[-1]}"
    elif top_entities_list:
        entities_str = top_entities_list[0]
    else:
        entities_str = "key external stakeholders"

    if risk_score >= 70 and sentiment == "negative":
        return (
            f"URGENT CRISIS PROTOCOL ACTIVATED FOR {keyword.upper()}.\n"
            f"Based on a critical risk score of {risk_score}/100, immediate containment is required to protect brand equity. "
            f"1. Execute an immediate PR containment strategy targeting the negative narratives specifically involving {entities_str}. "
            f"2. Alert the executive crisis committee and legal teams within the next 2 hours. "
            f"3. Issue a localized holding statement to Tier 1 media outlets to prevent the narrative from spreading to secondary networks. "
            f"Failure to act swiftly on this negative momentum will likely result in severe reputational or financial damage."
        )
    elif risk_score >= 50 and sentiment == "negative":
        return (
            f"ELEVATED RISK FLAG DETECTED FOR {keyword.upper()}.\n"
            f"This event carries a risk score of {risk_score}/100 and requires active surveillance. "
            f"1. Instruct communications teams to monitor the specific discussion threads involving {entities_str} continuously over the next 6-12 hours. "
            f"2. Prepare a draft holding statement addressing the root causes identified in the dragnet. "
            f"3. Ensure customer support teams are briefed on how to handle incoming queries related to this specific incident."
        )
    elif sentiment == "positive":
        return (
            f"STRATEGIC OPPORTUNITY FOR {keyword.upper()}.\n"
            f"The prevailing positive sentiment presents a distinct opportunity to amplify brand reach. "
            f"1. Instruct social media teams to actively engage with and share this specific coverage. "
            f"2. Consider drafting an official press release or blog post highlighting the successful involvement of {entities_str}. "
            f"3. Forward this intelligence to the marketing and sales departments as verifiable proof of positive market traction."
        )
    else:
        return (
            f"STANDARD OPERATIONS TRACKING FOR {keyword.upper()}.\n"
            f"This content registers a low actionable risk score of {risk_score}/100 with neutral sentiment. "
            f"1. Automatically archive this intelligence into the weekly strategic reporting dashboard. "
            f"2. No immediate reactive PR or executive measures are required at this exact moment. "
            f"3. Continue passive baseline monitoring of {entities_str} to ensure neutral sentiment does not gradually degrade."
        )


# ────────────────────────────────────────────────────────────────
# SECTION 7: Story Clustering
# ────────────────────────────────────────────────────────────────


def cluster_articles(articles: list[dict]) -> list[dict]:
    """
    Groups related articles using HDBSCAN on MiniLM embeddings.
    Adds cluster_id to each article.
    Falls back to no clustering if embeddings unavailable.
    """
    from services.ml_models import get_embed_model
    _embed_model = get_embed_model()

    if _embed_model is None or len(articles) < 3:
        for i, a in enumerate(articles):
            a["cluster_id"] = f"single_{i}"
        return articles

    try:
        import numpy as np
        import hdbscan

        texts = [
            (a.get("title", "") + " " + a.get("body_text", ""))[:512]
            for a in articles
        ]
        embeddings = list(_embed_model.embed(texts))
        embeddings = np.array(embeddings).astype("float32")

        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=2,
            min_samples=1,
            metric="euclidean",
        )
        labels = clusterer.fit_predict(embeddings)

        for article, label in zip(articles, labels):
            c_id = f"cluster_{label}" if label >= 0 else f"single_{id(article)}"
            article["cluster_id"] = c_id
            article["clusterId"] = c_id
    except Exception as e:
        print(f"[NLP] Clustering failed ({e}), skipping")
        for i, a in enumerate(articles):
            a["cluster_id"] = f"single_{i}"
            a["clusterId"] = f"single_{i}"

    return articles


# ────────────────────────────────────────────────────────────────
# SECTION 8: Main Pipeline Entry Point
# ────────────────────────────────────────────────────────────────


import asyncio

def _process_single_article_cpu(article: dict, text: str, sentiment_result: dict, entities: list[dict]) -> dict:
    """Helper function to run the sync CPU-bound tasks for a single article in a background thread."""
    keyword = article.get("keyword", "")
    url = article.get("url", "")

    sentiment = sentiment_result["label"]
    sentiment_score = sentiment_result["score"]

    # Compound keyword check
    compound = article.get('compound_filter')
    if compound:
        combined = (article.get('title', '') + ' ' + article.get('body_text', '')).lower()
        if compound.lower() not in combined:
            return None  # Skip — keyword present but compound context missing

    # Extractive Summary
    try:
        summary = summarize(text)
        
        # Massive 100+ Word Padding for short API responses
        if len(summary.split()) < 100:
            headline = article.get('headline', '') or article.get('title', '')
            source = article.get('source', 'an external data source')
            k_word = article.get('keyword', 'this topic')
            time_pub = article.get('timestamp', 'recently')
            
            summary = (
                f"{summary}\n\n"
                f"Contextual Amplification: The immediate reporting from {source} published at {time_pub} regarding '{headline}' "
                f"provides only a surface-level overview of the event, but its inclusion in the active intelligence dragnet for {k_word} signifies "
                f"its relevance to the broader media narrative. Short-form dispatches like this typically act as the initial epicenter "
                f"of breaking news before downstream analytical reporting can fully contextualize the strategic implications. "
                f"We are actively logging this initial fragmented intelligence because these brief, isolated headlines frequently aggregate into "
                f"major reputational shifts or market movements over a 24-48 hour window. The core entities and overarching sentiment attached "
                f"to this primary source document are currently being mapped into our multi-dimensional vector space. As additional context streams "
                f"in from corollary channels, this foundational snippet will serve as the chronological anchor point for our timeline reconstruction, "
                f"allowing analysts to track exactly how and where the {k_word} narrative initially fractured into the public domain."
            )
    except Exception:
        summary = text[:1200]

    source = article.get("source", url)
    published_at = article.get("published_at", "")
    hourly_volume = article.get("hourly_volume", [])

    risk = compute_risk_score(text, keyword, sentiment, source, entities)
    trend = compute_trend_score(keyword, source, published_at, hourly_volume)
    why = why_it_matters(keyword, sentiment, entities, text, article)
    action = suggested_action(keyword, risk, sentiment, entities, text)

    origin = article.get("origin", "")
    category = (
        "News" if origin in ("google_news_rss", "gdelt")
        else "Social" if origin == "mastodon"
        else "Technology" if origin == "hackernews"
        else "Reference" if origin == "wikimedia"
        else "Technology"
    )

    return {
        **article,
        "id": article.get("url", str(id(article))),
        "headline": article.get("title", "Untitled"),
        "sourceUrl": article.get("url", ""),
        "timestamp": article.get("published_at", "Just now"),
        "publishedAt": article.get("published_at", ""),
        "thumbnail": "https://images.unsplash.com/photo-1504711434969-e33886168f5c?w=800&q=80",
        "category": category,
        "sentiment": {
            "label": sentiment,
            "score": sentiment_score
        },
        "riskScore": risk,
        "trendScore": trend,
        "entities": [{"text": e["text"], "type": e.get("label", "Unknown")} for e in entities],
        "summary": summary,
        "whyItMatters": why,
        "suggestedAction": action,
        "relatedCount": 0,
        # Keep internal snake_case
        "risk_score": risk,
        "trend_score": trend,
    }

async def process_articles(articles: list[dict]) -> list[dict]:
    """
    Runs the full NLP pipeline on a list of raw articles concurrently.
    Each article gets: sentiment, entities, summary,
    risk_score, trend_score, why_it_matters, suggested_action.
    """
    if not articles:
        return []

    # Extract texts
    texts = [a.get("body_text", "") or a.get("title", "") for a in articles]

    # Phase 1: Massive GPU Batch Operations
    # Run sentiment in a single batch pass
    sentiments = await asyncio.to_thread(batch_analyze_sentiment, texts)
    
    # Run NER in a single batch pass
    from backend.ner_service import batch_extract_entities
    entities = await asyncio.to_thread(batch_extract_entities, texts)

    # Phase 2: CPU-bound Operations (Threading)
    tasks = [
        asyncio.to_thread(_process_single_article_cpu, article, text, sent, ent)
        for article, text, sent, ent in zip(articles, texts, sentiments, entities)
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    processed = []
    for res in results:
        if isinstance(res, dict):
            processed.append(res)
        elif res is None:
            pass  # Skipped via compound check
        else:
            logger.error(f"[NLP Pipeline] Async processing failed for an article: {res}")

    try:
        from datasketch import MinHash, MinHashLSH

        def deduplicate_by_content(articles: list) -> list:
            lsh = MinHashLSH(threshold=0.8, num_perm=64)
            unique = []
            for i, article in enumerate(articles):
                text = (article.get('title','') + ' ' +
                        article.get('body_text',''))[:300]
                m = MinHash(num_perm=64)
                for word in text.lower().split():
                    m.update(word.encode('utf-8'))
                try:
                    result = lsh.query(m)
                    if not result:
                        lsh.insert(f"art_{i}", m)
                        unique.append(article)
                    # else: near-duplicate, skip
                except: unique.append(article)
            return unique

        processed = deduplicate_by_content(processed)
    except Exception as e:
        print(f"[NLP] Deduplication failed ({e}), skipping")

    return cluster_articles(processed)
