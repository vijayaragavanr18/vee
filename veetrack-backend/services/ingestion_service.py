import os
import logging
from datetime import datetime, timedelta, timezone
import dateutil.parser
import feedparser
import httpx
from newspaper import Article as NewspaperArticle

from database import async_session_factory
from models import NewsSource, FetchLog

logger = logging.getLogger(__name__)

NEWSDATA_API_KEY = os.getenv("NEWSDATA_API_KEY")
FREENEWS_API_KEY = os.getenv("FREENEWS_API_KEY")
CURRENTS_API_KEY = os.getenv("CURRENTS_API_KEY")
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")

class IngestionService:
    def _filter_recent(self, articles: list[dict]) -> list[dict]:
        """Filters articles to only keep those published within the last 24 hours."""
        recent_articles = []
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=24)
        
        for article in articles:
            pub_date_str = article.get("published_at")
            if not pub_date_str:
                recent_articles.append(article) # Default to keeping if no date provided
                continue
                
            try:
                # Parse date, making it timezone-aware if it isn't already
                dt = dateutil.parser.parse(pub_date_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                
                if dt > cutoff:
                    recent_articles.append(article)
            except Exception as e:
                # If we absolutely cannot parse the date, we err on the side of caution and keep it
                logger.warning(f"Could not parse date {pub_date_str}: {e}")
                recent_articles.append(article)
                
        return recent_articles

    async def extract_text(self, url: str) -> str:
        """Extracts main body text from a raw URL using newspaper3k."""
        try:
            article = NewspaperArticle(url)
            article.download()
            article.parse()
            return article.text
        except Exception as e:
            logger.error(f"Failed to extract text from {url}: {e}")
            return ""

    async def fetch_rss(self, url: str) -> list[dict]:
        """Fetches and parses an RSS feed."""
        try:
            feed = feedparser.parse(url)
            articles = []
            for entry in feed.entries[:20]: # Limit to 20 per fetch
                articles.append({
                    "title": entry.get("title", ""),
                    "url": entry.get("link", ""),
                    "published_at": entry.get("published", datetime.now(timezone.utc).isoformat())
                })
            return self._filter_recent(articles)
        except Exception as e:
            logger.error(f"RSS fetch failed for {url}: {e}")
            raise e

    async def fetch_url(self, url: str) -> list[dict]:
        """Custom URL polling, assumes single article or simple sitemap."""
        title = "Direct URL Fetch"
        articles = [{"title": title, "url": url, "published_at": datetime.now(timezone.utc).isoformat()}]
        return self._filter_recent(articles)

    async def fetch_newsdata(self, url: str) -> list[dict]:
        """Fetches from NewsData.io"""
        if not NEWSDATA_API_KEY:
            raise ValueError("NEWSDATA_API_KEY is not set.")
        full_url = f"{url}&apikey={NEWSDATA_API_KEY}" if "?" in url else f"{url}?apikey={NEWSDATA_API_KEY}"
        async with httpx.AsyncClient() as client:
            res = await client.get(full_url)
            res.raise_for_status()
            data = res.json()
            articles = []
            for item in data.get("results", [])[:20]:
                articles.append({
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "published_at": item.get("pubDate", datetime.now(timezone.utc).isoformat())
                })
            return self._filter_recent(articles)

    async def fetch_freenews(self, url: str) -> list[dict]:
        """Fetches from FreeNewsAPI"""
        # Note: headers might be needed depending on API specifics
        headers = {"x-api-key": FREENEWS_API_KEY} if FREENEWS_API_KEY else {}
        async with httpx.AsyncClient() as client:
            res = await client.get(url, headers=headers)
            res.raise_for_status()
            data = res.json()
            articles = []
            for item in data.get("articles", [])[:20]:
                articles.append({
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "published_at": item.get("published_date", datetime.now(timezone.utc).isoformat())
                })
            return self._filter_recent(articles)

    async def fetch_currents(self, url: str) -> list[dict]:
        """Fetches from Currents API"""
        if not CURRENTS_API_KEY:
            raise ValueError("CURRENTS_API_KEY is not set.")
        full_url = f"{url}&apiKey={CURRENTS_API_KEY}" if "?" in url else f"{url}?apiKey={CURRENTS_API_KEY}"
        async with httpx.AsyncClient() as client:
            res = await client.get(full_url)
            res.raise_for_status()
            data = res.json()
            articles = []
            for item in data.get("news", [])[:20]:
                articles.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "published_at": item.get("published", datetime.now(timezone.utc).isoformat())
                })
            return self._filter_recent(articles)

    async def fetch_gdelt(self, url: str) -> list[dict]:
        """Fetches from GDELT 2.0 API"""
        async with httpx.AsyncClient() as client:
            res = await client.get(url)
            res.raise_for_status()
            data = res.json()
            articles = []
            for item in data.get("articles", [])[:20]:
                articles.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "published_at": item.get("seendate", datetime.now(timezone.utc).isoformat())
                })
            return self._filter_recent(articles)

    async def fetch_youtube(self, video_id: str) -> list[dict]:
        """Fetches transcript from YouTube API"""
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
            full_text = " ".join([t['text'] for t in transcript_list])
            return [{
                "title": f"YouTube Transcript: {video_id}",
                "url": f"https://youtube.com/watch?v={video_id}",
                "published_at": datetime.now(timezone.utc).isoformat(),
                "body_text": full_text # Special case: text already extracted
            }]
        except Exception as e:
            logger.error(f"YouTube transcript failed for {video_id}: {e}")
            raise e

    async def fetch_reddit(self, subreddit: str) -> list[dict]:
        """Fetches posts from Reddit API"""
        try:
            import praw
            reddit = praw.Reddit(
                client_id=REDDIT_CLIENT_ID,
                client_secret=REDDIT_CLIENT_SECRET,
                user_agent="VeeTrack/1.0"
            )
            sub = reddit.subreddit(subreddit)
            articles = []
            for post in sub.hot(limit=20):
                if not post.is_self: # link post
                    articles.append({
                        "title": post.title,
                        "url": post.url,
                        "published_at": datetime.fromtimestamp(post.created_utc, tz=timezone.utc).isoformat()
                    })
                else: # text post
                    articles.append({
                        "title": post.title,
                        "url": post.url,
                        "body_text": post.selftext,
                        "published_at": datetime.fromtimestamp(post.created_utc, tz=timezone.utc).isoformat()
                    })
            return self._filter_recent(articles)
        except Exception as e:
            logger.error(f"Reddit fetch failed for {subreddit}: {e}")
            raise e

    async def fetch_reddit_free(self, keyword: str) -> list[dict]:
        """Fetches from Reddit via DuckDuckGo to bypass API blocks"""
        try:
            from ddgs import DDGS
            articles = []
            
            with DDGS() as ddgs:
                results = ddgs.text(f"site:reddit.com {keyword}", max_results=10)
                for res in results:
                    articles.append({
                        "title": res.get("title", ""),
                        "url": res.get("href", ""),
                        "body_text": res.get("body", ""),
                        "published_at": datetime.now(timezone.utc).isoformat()
                    })
            return self._filter_recent(articles)
        except Exception as e:
            # Silently pass to avoid cluttering CLI
            pass
            return []

    async def fetch_youtube_free(self, keyword: str) -> list[dict]:
        """Searches YouTube and extracts transcripts without API keys"""
        try:
            from youtubesearchpython import VideosSearch
            from youtube_transcript_api import YouTubeTranscriptApi
            
            # Search YouTube for top 5 videos matching keyword
            videos_search = VideosSearch(keyword, limit=5)
            results = videos_search.result()
            
            articles = []
            for video in results.get("result", []):
                video_id = video.get("id")
                title = video.get("title", "")
                link = video.get("link", "")
                published_time = video.get("publishedTime", "")
                
                # Try to get transcript
                try:
                    transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
                    full_text = " ".join([t['text'] for t in transcript_list])
                    
                    articles.append({
                        "title": f"YouTube: {title}",
                        "url": link,
                        # We use now() as we can't easily parse YouTube's relative time "2 days ago" perfectly,
                        # but we want it to pass the _filter_recent check if it's relevant.
                        "published_at": datetime.now(timezone.utc).isoformat(),
                        "body_text": full_text
                    })
                except Exception:
                    # Video might not have closed captions
                    pass
            
            return self._filter_recent(articles)
        except Exception as e:
            logger.error(f"Free YouTube fetch failed for {keyword}: {e}")
            raise e

ingestion_service = IngestionService()
