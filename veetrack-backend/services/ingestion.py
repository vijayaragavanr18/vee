"""
VeeTrack Ingestion Service — Async fetch from all 5 data sources.

Each source fetcher runs independently with try/except so one
failure never breaks the rest. All 5 sources run in parallel
per keyword using asyncio.gather().

Sources:
1. Google News RSS (feedparser)
2. GDELT 2.0 DOC API
3. Hacker News (Algolia)
4. Mastodon (search endpoint ONLY — trending/public are dead)
5. Wikimedia Recent Changes
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

import httpx

try:
    import feedparser

    HAS_FEEDPARSER = True
except ImportError:
    HAS_FEEDPARSER = False

logger = logging.getLogger(__name__)


# ── Helper ──────────────────────────────────────────────────────


def _strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    import re

    return re.sub(r"<[^>]+>", "", text).strip()


def _get_client(timeout: int = 10, follow_redirects: bool = False) -> httpx.AsyncClient:
    """Return an httpx client with proxy enabled if PROXY_URL is set in environment."""
    import os
    proxy = os.getenv("PROXY_URL")
    
    if proxy:
        return httpx.AsyncClient(timeout=timeout, follow_redirects=follow_redirects, proxy=proxy)
    return httpx.AsyncClient(timeout=timeout, follow_redirects=follow_redirects)


def deduplicate_by_url(articles: list[dict]) -> list[dict]:
    """Remove articles with duplicate URLs (keep first occurrence)."""
    seen: set[str] = set()
    result: list[dict] = []
    for a in articles:
        key = a.get("url", "").lower().strip()
        if key and key not in seen:
            seen.add(key)
            result.append(a)
    return result


# ── Source 1: Google News RSS ───────────────────────────────────


async def fetch_google_news_rss(keyword: str, days: int = 5) -> list[dict]:
    """Fetch from Google News RSS feed for a keyword."""
    if not HAS_FEEDPARSER:
        logger.warning("[Google News RSS] feedparser not installed, skipping")
        return []

    url = (
        f"https://news.google.com/rss/search"
        f"?q={quote_plus(keyword)}&hl=en-IN&gl=IN&ceid=IN:en"
    )
    try:
        async with _get_client(timeout=10) as client:
            resp = await client.get(url)
        feed = feedparser.parse(resp.text)
        since = datetime.now(timezone.utc) - timedelta(days=days)
        articles = []
        for entry in feed.entries:
            try:
                published = datetime(
                    *entry.published_parsed[:6], tzinfo=timezone.utc
                )
                if published < since:
                    continue
            except (AttributeError, TypeError):
                published = None

            source_title = "Google News"
            try:
                source_title = entry.get("source", {}).get("title", "Google News")
            except Exception:
                pass

            articles.append(
                {
                    "title": entry.get("title", ""),
                    "url": entry.get("link", ""),
                    "published_at": (
                        published.isoformat() if published else datetime.now(timezone.utc).isoformat()
                    ),
                    "source": source_title,
                    "body_text": _strip_html(entry.get("summary", "")),
                    "origin": "google_news_rss",
                }
            )
        return articles
    except Exception as e:
        logger.warning("[Google News RSS] Error for '%s': %s", keyword, e)
        return []


# ── Source 1.5: Indian Trade RSS ────────────────────────────────

INDIA_TRADE_RSS_FEEDS = [
    # OTT/Media trade press — most important for Vee Tech clients
    "https://www.exchange4media.com/rss/rss.aspx",
    "https://www.indiantelevision.com/rss.xml",
    "https://www.afaqs.com/rss/news",
    "https://www.bestmediainfo.com/feed",

    # General business — high authority
    "https://economictimes.indiatimes.com/rssfeedstopstories.cms",
    "https://www.livemint.com/rss/companies",
    "https://www.businessstandard.com/rss/latest.rss",
    "https://www.thehindu.com/business/feeder/default.rss",

    # Tech
    "https://inc42.com/feed/",
    "https://entrackr.com/feed/",
]

async def fetch_trade_rss(keyword: str, days: int = 5) -> list[dict]:
    """Fetch from static Indian trade RSS feeds and filter by keyword."""
    if not HAS_FEEDPARSER:
        return []

    since = datetime.now(timezone.utc) - timedelta(days=days)
    articles = []
    kw_lower = keyword.lower()

    async def _fetch_feed(url: str):
        try:
            async with _get_client(timeout=10, follow_redirects=True) as client:
                resp = await client.get(url)
            feed = feedparser.parse(resp.text)
            feed_articles = []
            for entry in feed.entries:
                try:
                    published = datetime(
                        *entry.published_parsed[:6], tzinfo=timezone.utc
                    )
                    if published < since:
                        continue
                except (AttributeError, TypeError):
                    published = None

                title = entry.get("title", "")
                summary = _strip_html(entry.get("summary", ""))
                
                if kw_lower not in title.lower() and kw_lower not in summary.lower():
                    continue

                source_title = feed.feed.get("title", "Trade Press")
                
                feed_articles.append(
                    {
                        "title": title,
                        "url": entry.get("link", ""),
                        "published_at": (
                            published.isoformat() if published else datetime.now(timezone.utc).isoformat()
                        ),
                        "source": source_title,
                        "body_text": summary,
                        "origin": "trade_rss",
                    }
                )
            return feed_articles
        except Exception as e:
            logger.debug("[Trade RSS] Error for feed %s: %s", url, e)
            return []

    tasks = [_fetch_feed(url) for url in INDIA_TRADE_RSS_FEEDS]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for res in results:
        if isinstance(res, list):
            articles.extend(res)
            
    return articles


# ── Source 2: GDELT 2.0 ────────────────────────────────────────


async def fetch_gdelt(keyword: str) -> list[dict]:
    """Fetch from GDELT DOC API."""
    url = (
        f"https://api.gdeltproject.org/api/v2/doc/doc"
        f"?query={quote_plus(keyword)}&mode=artlist"
        f"&maxrecords=10&format=json&sourcelang=english"
    )
    try:
        async with _get_client(timeout=15) as client:
            resp = await client.get(url)
        data = resp.json()
        articles = []

        async def fetch_full_text(article_url: str) -> str:
            try:
                import trafilatura
                async with _get_client(timeout=10, follow_redirects=True) as txt_client:
                    r = await txt_client.get(article_url)
                extracted = trafilatura.extract(r.text)
                return extracted if extracted else ""
            except Exception:
                return ""

        for item in data.get("articles", []):
            item_url = item.get("url", "")
            body_text = item.get("title", "")
            if item_url:
                try:
                    full = await fetch_full_text(item_url)
                    if full:
                        body_text = full
                except Exception:
                    pass

            articles.append(
                {
                    "title": item.get("title", ""),
                    "url": item_url,
                    "published_at": item.get("seendate", ""),
                    "source": item.get("domain", "GDELT"),
                    "body_text": body_text,
                    "origin": "gdelt",
                }
            )
        return articles
    except Exception as e:
        logger.warning("[GDELT] Error for '%s': %s", keyword, e)
        return []


# ── Source 3: Hacker News (Algolia) ─────────────────────────────


async def fetch_hackernews(keyword: str, days: int = 5) -> list[dict]:
    """Fetch from Hacker News via Algolia search API."""
    since = int(
        (datetime.now(timezone.utc) - timedelta(days=days)).timestamp()
    )
    url = (
        f"https://hn.algolia.com/api/v1/search"
        f"?query={quote_plus(keyword)}&tags=story"
        f"&numericFilters=created_at_i>{since}&hitsPerPage=10"
    )
    try:
        async with _get_client(timeout=10) as client:
            resp = await client.get(url)
        data = resp.json()
        articles = []
        for hit in data.get("hits", []):
            if not hit.get("url"):
                continue
            articles.append(
                {
                    "title": hit.get("title", ""),
                    "url": hit.get("url", ""),
                    "published_at": hit.get("created_at", ""),
                    "source": "Hacker News",
                    "body_text": hit.get("title", ""),
                    "origin": "hackernews",
                }
            )
        return articles
    except Exception as e:
        logger.warning("[HackerNews] Error for '%s': %s", keyword, e)
        return []


# ── Source 4: Mastodon (search endpoint ONLY) ───────────────────


async def fetch_mastodon(keyword: str) -> list[dict]:
    """
    Fetch from Mastodon search endpoint ONLY.

    NOTE: /api/v1/timelines/public returns 422.
    NOTE: /api/v1/trends/statuses returns 404.
    Only /api/v2/search works reliably.
    """
    url = (
        f"https://mastodon.social/api/v2/search"
        f"?q={quote_plus(keyword)}&type=statuses&limit=10"
    )
    try:
        async with _get_client(timeout=10) as client:
            resp = await client.get(url)
        data = resp.json()
        articles = []
        for status in data.get("statuses", []):
            content = _strip_html(status.get("content", ""))
            articles.append(
                {
                    "title": content[:100] if content else "Mastodon post",
                    "url": status.get("url", ""),
                    "published_at": status.get("created_at", ""),
                    "source": "Mastodon",
                    "body_text": content,
                    "origin": "mastodon",
                }
            )
        return articles
    except Exception as e:
        logger.warning("[Mastodon] Error for '%s': %s", keyword, e)
        return []


# ── Source 5: Wikimedia Recent Changes ──────────────────────────


async def fetch_wikimedia(keyword: str) -> list[dict]:
    """Fetch from Wikipedia Recent Changes API."""
    url = (
        f"https://en.wikipedia.org/w/api.php"
        f"?action=query&list=recentchanges"
        f"&rcnamespace=0&rclimit=5"
        f"&rcsearch={quote_plus(keyword)}&format=json"
    )
    try:
        async with _get_client(timeout=10) as client:
            resp = await client.get(
                url,
                headers={"User-Agent": "VeeTrack/1.0 (media intelligence)"},
            )
        data = resp.json()
        articles = []
        for change in data.get("query", {}).get("recentchanges", []):
            title = change.get("title", "")
            articles.append(
                {
                    "title": title,
                    "url": f"https://en.wikipedia.org/wiki/{quote_plus(title)}",
                    "published_at": change.get("timestamp", ""),
                    "source": "Wikipedia",
                    "body_text": title,
                    "origin": "wikimedia",
                }
            )
        return articles
    except Exception as e:
        logger.warning("[Wikimedia] Error for '%s': %s", keyword, e)
        return []


# ── Source 6: Reddit (Free JSON endpoint) ───────────────────────


async def fetch_reddit(keyword: str, limit: int = 10) -> list[dict]:
    """Fetch recent posts from Reddit using the free JSON search endpoint."""
    url = f"https://www.reddit.com/search.json?q={quote_plus(keyword)}&sort=new&limit={limit}"
    try:
        async with _get_client(timeout=10, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "VeeTrack/1.0 (media intelligence bot)"})
        data = resp.json()
        articles = []
        for child in data.get("data", {}).get("children", []):
            post = child.get("data", {})
            articles.append({
                "title": post.get("title", ""),
                "url": f"https://reddit.com{post.get('permalink', '')}",
                "published_at": datetime.fromtimestamp(post.get("created_utc", 0), timezone.utc).isoformat(),
                "source": f"Reddit (r/{post.get('subreddit', 'unknown')})",
                "body_text": post.get("selftext", ""),
                "origin": "reddit",
            })
        return articles
    except Exception as e:
        logger.warning("[Reddit] Error for '%s': %s", keyword, e)
        return []


# ── Source 7: YouTube Transcripts (Free API) ────────────────────


async def fetch_youtube(keyword: str, limit: int = 5) -> list[dict]:
    """Search YouTube and download transcripts for the top videos."""
    try:
        from youtubesearchpython import VideosSearch
        from youtube_transcript_api import YouTubeTranscriptApi
        
        # Run synchronous search in an executor to avoid blocking async loop
        loop = asyncio.get_running_loop()
        videosSearch = VideosSearch(keyword, limit=limit)
        results = await loop.run_in_executor(None, videosSearch.result)
        
        articles = []
        for video in results.get("result", []):
            video_id = video.get("id")
            
            transcript_text = ""
            try:
                # Fetch and Auto-Translate transcript to English
                def _get_en_transcript(vid):
                    transcript_list = YouTubeTranscriptApi.list_transcripts(vid)
                    try:
                        return transcript_list.find_transcript(['en']).fetch()
                    except Exception:
                        for transcript in transcript_list:
                            if transcript.is_translatable:
                                return transcript.translate('en').fetch()
                        raise Exception("No translatable transcript")
                        
                fetched_transcript = await loop.run_in_executor(None, _get_en_transcript, video_id)
                transcript_text = " ".join([t['text'] for t in fetched_transcript])
            except Exception:
                # Fallback to description snippet if no subtitles exist
                snippets = video.get("descriptionSnippet", [])
                if snippets:
                    transcript_text = " ".join([s.get("text", "") for s in snippets])

            articles.append({
                "title": video.get("title", ""),
                "url": video.get("link", ""),
                "published_at": datetime.now(timezone.utc).isoformat(),
                "source": f"YouTube ({video.get('channel', {}).get('name', 'YouTube')})",
                "body_text": transcript_text[:5000], # Limit length to save memory
                "origin": "youtube",
            })
        return articles
    except Exception as e:
        logger.warning("[YouTube] Error for '%s': %s", keyword, e)
        return []


# ── Source 8: StackOverflow (Free API) ──────────────────────────


async def fetch_stackoverflow(keyword: str) -> list[dict]:
    """Fetch recent questions from StackOverflow matching the keyword."""
    # Using 'withbody' filter to get the question text
    url = f"https://api.stackexchange.com/2.3/search?order=desc&sort=activity&intitle={quote_plus(keyword)}&site=stackoverflow&filter=withbody"
    try:
        async with _get_client(timeout=10) as client:
            resp = await client.get(url)
        data = resp.json()
        articles = []
        for item in data.get("items", [])[:10]:
            articles.append({
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "published_at": datetime.fromtimestamp(item.get("creation_date", 0), timezone.utc).isoformat(),
                "source": "StackOverflow",
                "body_text": _strip_html(item.get("body", "")),
                "origin": "stackoverflow",
            })
        return articles
    except Exception as e:
        logger.warning("[StackOverflow] Error for '%s': %s", keyword, e)
        return []


# ── Source 9: Yahoo News/Finance RSS (Free) ─────────────────────


async def fetch_yahoo_finance(keyword: str) -> list[dict]:
    """Fetch from Yahoo News/Finance RSS."""
    if not HAS_FEEDPARSER:
        return []
    url = f"https://news.yahoo.com/rss/search?p={quote_plus(keyword)}"
    try:
        async with _get_client(timeout=10) as client:
            resp = await client.get(url)
        feed = feedparser.parse(resp.text)
        articles = []
        for entry in feed.entries[:10]:
            try:
                published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            except Exception:
                published = datetime.now(timezone.utc)

            articles.append({
                "title": entry.get("title", ""),
                "url": entry.get("link", ""),
                "published_at": published.isoformat(),
                "source": entry.get("source", {}).get("title", "Yahoo News"),
                "body_text": _strip_html(entry.get("summary", "")),
                "origin": "yahoo_finance",
            })
        return articles
    except Exception as e:
        logger.warning("[Yahoo Finance] Error for '%s': %s", keyword, e)
        return []


# ── Source 10: App Store Reviews (Free API) ──────────────────────


async def fetch_app_store_reviews(keyword: str) -> list[dict]:
    """Search iTunes for the app and fetch recent 1-star/2-star reviews."""
    search_url = f"https://itunes.apple.com/search?term={quote_plus(keyword)}&entity=software&limit=1"
    try:
        async with _get_client(timeout=10) as client:
            search_resp = await client.get(search_url)
        search_data = search_resp.json()
        if not search_data.get("results"):
            return []
        
        app_id = search_data["results"][0]["trackId"]
        app_name = search_data["results"][0]["trackName"]
        
        reviews_url = f"https://itunes.apple.com/us/rss/customerreviews/id={app_id}/sortBy=mostRecent/json"
        async with _get_client(timeout=10) as client:
            reviews_resp = await client.get(reviews_url)
        reviews_data = reviews_resp.json()
        
        articles = []
        entries = reviews_data.get("feed", {}).get("entry", [])
        if isinstance(entries, dict):
            entries = [entries]
            
        for entry in entries[:10]:
            if not isinstance(entry, dict) or "title" not in entry:
                continue
            rating = entry.get("im:rating", {}).get("label", "5")
            # Only track bad reviews (1, 2, or 3 stars) for crisis detection
            if int(rating) > 3:
                continue
                
            title = entry.get("title", {}).get("label", "")
            content = entry.get("content", {}).get("label", "")
            
            articles.append({
                "title": f"{rating} Star Review: {title}",
                "url": search_data["results"][0].get("trackViewUrl", ""),
                "published_at": datetime.now(timezone.utc).isoformat(),
                "source": f"App Store ({app_name})",
                "body_text": content,
                "origin": "app_store",
            })
        return articles
    except Exception as e:
        logger.warning("[App Store] Error for '%s': %s", keyword, e)
        return []


# ── Source 11: NewsData.io (Requires API Key) ───────────────────


async def fetch_newsdata(keyword: str) -> list[dict]:
    """Fetch from NewsData.io if API key is present."""
    import os
    api_key = os.getenv("NEWSDATA_API_KEY")
    if not api_key:
        return []
        
    url = f"https://newsdata.io/api/1/news?apikey={api_key}&q={quote_plus(keyword)}&language=en"
    try:
        async with _get_client(timeout=10) as client:
            resp = await client.get(url)
        data = resp.json()
        articles = []
        for item in data.get("results", [])[:10]:
            body_text = item.get("content") or item.get("description", "")
            articles.append({
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "published_at": item.get("pubDate", datetime.now(timezone.utc).isoformat()),
                "source": item.get("source_id", "NewsData.io"),
                "body_text": body_text,
                "origin": "newsdata",
            })
        return articles
    except Exception as e:
        logger.warning("[NewsData.io] Error for '%s': %s", keyword, e)
        return []


# ── Source 12: Alpha Vantage (Requires API Key) ─────────────────


async def fetch_alpha_vantage(keyword: str) -> list[dict]:
    """Fetch from Alpha Vantage if API key is present."""
    import os
    api_key = os.getenv("ALPHAVANTAGE_API_KEY")
    if not api_key:
        return []
        
    url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers={quote_plus(keyword)}&apikey={api_key}"
    try:
        async with _get_client(timeout=10) as client:
            resp = await client.get(url)
        data = resp.json()
        articles = []
        for item in data.get("feed", [])[:5]:
            articles.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "published_at": datetime.now(timezone.utc).isoformat(),
                "source": item.get("source", "Alpha Vantage"),
                "body_text": item.get("summary", ""),
                "origin": "alpha_vantage",
            })
        return articles
    except Exception as e:
        logger.warning("[Alpha Vantage] Error for '%s': %s", keyword, e)
        return []

# ── Background Pre-Scraping ─────────────────────────────────────

async def background_pre_scrape(articles: list[dict]):
    """
    Silently scrapes the full text of articles in the background and saves to DiskCache.
    This guarantees 0-second load times when the user clicks 'Read Full Story'.
    """
    from core.cache_client import get_cache
    cache = await get_cache()
    
    # We only pre-scrape the top 10 articles to save resources
    for article in articles[:10]:
        url = article.get("url")
        if not url or not url.startswith("http"):
            continue
            
        cache_key = f"scrape:{url}"
        existing = await cache.get(cache_key)
        if existing:
            continue
            
        logger.info(f"[Pre-Fetch] Silently scraping {url} in background...")
        try:
            # 1. Try Jina Reader
            async with httpx.AsyncClient(timeout=10.0) as fetch_client:
                jina_res = await fetch_client.get(f"https://r.jina.ai/{url}")
                if jina_res.status_code == 200 and len(jina_res.text) > 500:
                    await cache.set(cache_key, jina_res.text[:15000], ex=86400 * 7) # Cache for 7 days
                    continue
        except Exception:
            pass
            
        # 2. Try Crawl4AI fallback
        try:
            from crawl4ai import AsyncWebCrawler
            async with AsyncWebCrawler(verbose=False) as crawler:
                result = await crawler.arun(url=url, bypass_cache=True)
                if result and result.markdown:
                    await cache.set(cache_key, result.markdown[:15000], ex=86400 * 7)
        except Exception as e:
            logger.debug(f"[Pre-Fetch] Failed to pre-scrape {url}: {e}")


# ── Parallel Fetch Orchestrator ─────────────────────────────────


async def fetch_all_sources(
    keywords: list[str], days: int = 5
) -> list[dict]:
    """
    Fetch from all 5 sources in parallel for each keyword.
    Returns deduplicated, merged article list.
    """
    all_articles: list[dict] = []

    for keyword in keywords:
        results = await asyncio.gather(
            fetch_google_news_rss(keyword, days),
            fetch_trade_rss(keyword, days),
            fetch_gdelt(keyword),
            fetch_hackernews(keyword, days),
            fetch_mastodon(keyword),
            fetch_wikimedia(keyword),
            fetch_reddit(keyword),
            fetch_youtube(keyword),
            fetch_stackoverflow(keyword),
            fetch_yahoo_finance(keyword),
            fetch_app_store_reviews(keyword),
            fetch_newsdata(keyword),
            fetch_alpha_vantage(keyword),
            return_exceptions=True,
        )
        for batch in results:
            if isinstance(batch, list):
                for article in batch:
                    article["keyword"] = keyword
                all_articles.extend(batch)
            elif isinstance(batch, Exception):
                logger.warning(
                    "[Ingestion] Source failed for '%s': %s", keyword, batch
                )

    return deduplicate_by_url(all_articles)
