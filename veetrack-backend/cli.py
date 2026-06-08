import asyncio
import os
import sys
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box

import sys
import warnings

# Suppress harmless DuckDuckGo/lxml DeprecationWarnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Fix Windows console unicode issues (e.g. for Indian Rupee symbol)
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Ensure imports work regardless of execution location
sys.path.append(os.path.dirname(__file__))

# Load env for API keys BEFORE importing services
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from services.ingestion_service import ingestion_service
from services.nlp_pipeline import process_articles

console = Console()

async def main(keyword: str):
    console.rule(f"[bold blue]VeeTrack Intelligence CLI - Tracking: {keyword}[/]")
    
    raw_articles = []
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        # Phase 1: Ingestion & Model Loading
        task_ingest = progress.add_task("[cyan]Fetching live data & booting AI models in parallel...", total=None)
        
        # Start booting massive PyTorch models in the background instantly
        from services.ml_models import init_models
        model_load_task = asyncio.create_task(asyncio.to_thread(init_models))
        
        # Define API endpoints
        newsdata_url = f"https://newsdata.io/api/1/news?q={keyword}&language=en"
        freenews_url = f"https://freenews.org/api/v1/search?q={keyword}&lang=en"
        currents_url = f"https://api.currentsapi.services/v1/search?keywords={keyword}&language=en&hours_published=24"
        gdelt_url = f"https://api.gdeltproject.org/api/v2/doc/doc?query={keyword}&mode=artlist&format=json&timespan=1d"

        # Fire all Internet requests concurrently
        async def fetch_source(fetch_func, src_name, *args):
            try:
                data = await fetch_func(*args)
                for a in data:
                    a['keyword'] = keyword
                    a['source'] = src_name
                return data
            except Exception:
                return []

        api_tasks = [
            fetch_source(ingestion_service.fetch_newsdata, 'NewsData', newsdata_url),
            fetch_source(ingestion_service.fetch_freenews, 'FreeNews', freenews_url),
            fetch_source(ingestion_service.fetch_currents, 'Currents', currents_url),
            fetch_source(ingestion_service.fetch_gdelt, 'GDELT', gdelt_url),
            fetch_source(ingestion_service.fetch_reddit_free, 'Reddit', keyword),
            fetch_source(ingestion_service.fetch_youtube_free, 'YouTube', keyword)
        ]
        
        api_results = await asyncio.gather(*api_tasks)
        for res in api_results:
            raw_articles.extend(res)

        # Wait for PyTorch models to finish booting in the background
        await model_load_task
        progress.update(task_ingest, completed=True)
        
        if not raw_articles:
            console.print(f"[red]No articles found for '{keyword}' within the last 24 hours.[/]")
            return
            
        # Phase 2: NLP Pipeline
        task_nlp = progress.add_task(f"[magenta]Passing {len(raw_articles)} raw articles through AI pipeline...", total=None)
        processed_articles = await process_articles(raw_articles)
        progress.update(task_nlp, completed=True)
        
    # Phase 3: Reporting
    console.print(f"\n[bold green]Pipeline Complete![/] Processed {len(processed_articles)} unique articles.\n")
    
    # Global Stats Table
    table = Table(title="Global Intelligence Stats", box=box.ROUNDED)
    table.add_column("Total Articles", justify="center", style="cyan")
    table.add_column("Highest Risk Score", justify="center", style="red")
    table.add_column("Average Sentiment", justify="center", style="green")
    
    highest_risk = max([a.get('risk_score', 0) for a in processed_articles]) if processed_articles else 0
    negatives = len([a for a in processed_articles if a.get('sentiment', {}).get('label') == 'negative'])
    positives = len([a for a in processed_articles if a.get('sentiment', {}).get('label') == 'positive'])
    
    if negatives > positives:
        avg_sent = "[red]Negative[/]"
    elif positives > negatives:
        avg_sent = "[green]Positive[/]"
    else:
        avg_sent = "[yellow]Neutral[/]"
        
    table.add_row(str(len(processed_articles)), str(highest_risk), avg_sent)
    console.print(table)
    console.print("\n")
    
    # Sort by risk score and grab top 5
    processed_articles.sort(key=lambda x: x.get('risk_score', 0), reverse=True)
    
    for idx, article in enumerate(processed_articles[:20]):
        risk = article.get('risk_score', 0)
        risk_color = "red" if risk >= 70 else "yellow" if risk >= 40 else "green"
        
        sent = article.get('sentiment', {}).get('label', 'neutral')
        sent_color = "red" if sent == "negative" else "green" if sent == "positive" else "yellow"
        
        entities_text = ", ".join([e['text'] for e in article.get('entities', [])[:5]])
        if not entities_text:
            entities_text = "None detected"
            
        # Fetch AI Narrative from LLM gracefully
        ai_narrative = "LLM Server is currently offline. Start the vLLM server to generate the 500+ word AI Narrative."
        try:
            from backend.llm_service import get_card
            import json
            raw_text = article.get('body_text', '') or article.get('title', '')
            raw_entities = [{"text": e['text'], "label": e['type']} for e in article.get('entities', [])]
            card_json = await get_card(article.get('url', str(idx)), raw_text, raw_entities)
            if card_json:
                card_data = json.loads(card_json)
                ai_narrative = card_data.get('narrative', ai_narrative)
        except Exception as e:
            pass
            
        content = (
            f"[bold]Source:[/] {article.get('source', 'Unknown')}\n"
            f"[bold]Published:[/] {article.get('timestamp', 'Unknown')}\n\n"
            f"[bold]Risk Score:[/] [{risk_color}]{risk}/100[/]\n"
            f"[bold]Sentiment:[/] [{sent_color}]{sent.title()}[/]\n"
            f"[bold]Key Entities:[/] {entities_text}\n\n"
            f"[bold]What Happened:[/] {article.get('summary', 'No summary generated.')}\n\n"
            f"[bold blue]Why It Happened / Why It Matters:[/] {article.get('whyItMatters', '')}\n\n"
            f"[bold magenta]Suggested Action:[/] {article.get('suggestedAction', '')}\n\n"
            f"[bold cyan]AI Narrative (500+ words):[/]\n{ai_narrative}"
        )
        
        panel = Panel(
            content,
            title=f"[bold]{article.get('headline', 'Untitled')}[/]",
            border_style=risk_color,
            padding=(1, 2)
        )
        console.print(panel)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="VeeTrack CLI")
    parser.add_argument("keyword", type=str, help="Keyword to track and analyze")
    args = parser.parse_args()
    
    asyncio.run(main(args.keyword))
