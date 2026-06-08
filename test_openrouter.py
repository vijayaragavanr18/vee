import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv("veetrack-backend/.env")

async def run():
    async with httpx.AsyncClient() as client:
        response = await client.get("https://openrouter.ai/api/v1/models")
        if response.status_code == 200:
            models = response.json().get("data", [])
            free_models = [m["id"] for m in models if m["id"].endswith(":free")]
            print("Free models:", free_models)
        else:
            print("Failed", response.status_code)

asyncio.run(run())
