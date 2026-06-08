import asyncio
import httpx
import json

async def run():
    async with httpx.AsyncClient() as client:
        print("Sending request...")
        async with client.stream("POST", "http://localhost:8000/api/intelligence/stream-article", json={
            "title": "Amazon unveils new Proteus robot",
            "content": "Amazon unveiled a new robot called Proteus in Europe...",
            "url": "https://www.aboutamazon.com/news/operations/amazon-proteus-robot-europe-investme"
        }, timeout=120) as response:
            full_text = ""
            async for line in response.aiter_lines():
                if line.strip():
                    try:
                        data = json.loads(line)
                        if data.get("type") == "chunk":
                            chunk = data.get("chunk", "")
                            full_text += chunk
                            print(chunk, end="", flush=True)
                    except Exception as e:
                        print(f"Error parsing line: {line}")
            print("\n\n--- FULL TEXT LENGTH:", len(full_text), "characters ---")

asyncio.run(run())
