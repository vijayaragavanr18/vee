<div align="center">
  <img src="https://via.placeholder.com/150x150/000000/FFFFFF?text=VeeTrack" alt="VeeTrack Logo" width="100"/>
  <h1>VeeTrack: AI Media Intelligence</h1>
  <p>An enterprise-grade, privacy-first media tracking and intelligence platform powered by local AI.</p>
</div>

---

## 📖 Overview

VeeTrack is a modern monorepo platform designed to ingest, process, and summarize massive amounts of global and industry-specific news in real time. It acts as an autonomous PR analyst by tracking news feeds, identifying named entities, scoring public sentiment, grouping identical narratives, and generating executive briefs.

Because privacy is paramount, **VeeTrack relies entirely on open-source AI models running locally on your own hardware**, eliminating the need for expensive and invasive cloud APIs (like OpenAI).

---

## 🚀 Key Features

*   **Multi-Source Real-time Ingestion:** Automatically pulls and normalizes data from Google News, GDELT, HackerNews, Mastodon, and top Indian Trade Media (Economic Times, Exchange4media, Inc42).
*   **Locally Hosted AI Pipeline (No Cloud APIs):**
    *   **Named Entity Recognition (NER):** Uses `spaCy` (en_core_web_trf/sm) to identify companies, locations, and executives.
    *   **Sentiment Analysis:** Uses Cardiff NLP's Twitter RoBERTa model to detect positive, negative, and neutral tones.
    *   **Content Deduplication:** Uses `datasketch` (MinHash LSH) to identify near-duplicate articles and reduce noise.
    *   **Narrative Clustering:** Groups thousands of articles into readable "trends" using `HDBSCAN` and `SentenceTransformers`.
*   **Deep AI Narrative Generation:** Prompts a local Large Language Model (`llama3.2:1b` via Ollama) concurrently to output elaborate, full-page cognitive POV stories for every single article, mapping out exact facts and strategic business impacts.
*   **Modern 3D Interface:** A highly visual, gesture-driven frontend reader built with Vite, React 19, and Tailwind CSS.
*   **Zero-Config Local Execution:** No heavy Docker requirements. Natively compatible with both Linux and Windows.

---

## 🛠 Tech Stack

### Frontend (User Interface)
*   **Framework:** Vite, React 19 (Pure Standard JavaScript SPA)
*   **Styling:** Tailwind CSS v4, Lucide Icons
*   **Architecture:** High-performance "Thin Client" architecture connecting directly to the FastAPI backend.

### Backend (AI & Logic)
*   **Framework:** Python 3.12, FastAPI
*   **Databases:** SQLite (Celery Broker), DiskCache (Caching), FAISS (for vector retrieval during chat sessions).
*   **Task Queues:** Celery (background news fetching loop).
*   **Machine Learning:** PyTorch, HuggingFace Transformers, spaCy, scikit-learn.

---

## 💻 Getting Started (Local Development)

VeeTrack has been optimized to run completely natively on your machine without needing Docker or Redis.

### 1. Prerequisites
Ensure you have the following installed on your system:
*   **Python 3.10+** (and `pip`)
*   **Node.js 18+** (and `npm`)
*   **Ollama** (Required for AI Narrative generation)

### 2. Environment Setup
Create a `.env` file in the root directory:

```env
# Network configuration (Crucial: Use 127.0.0.1 instead of localhost for Node IPv6 compatibility)
VITE_BACKEND_URL=http://127.0.0.1:8000
BACKEND_URL=http://127.0.0.1:8000

# Optional: Local LLM Configuration
OLLAMA_URL=http://127.0.0.1:11434/api/generate
OLLAMA_MODEL=llama3.2:1b
```

### 3. Installation & Boot Up
You can install dependencies and start both the FastAPI backend and the Vite frontend concurrently with a single command.

**For Linux/Mac Users:**
```bash
npm run setup   # One-time installation of Python environments and ML models
npm run fresh   # Starts the backend and frontend concurrently
```

**For Windows Users:**
```cmd
npm run setup:win   # One-time installation of Python environments and ML models
npm run fresh:win   # Starts the backend and frontend concurrently
```

*The first time you run this, the backend will automatically download the necessary HuggingFace NLP models to your local cache. This may take a few minutes depending on your internet connection.*

### 4. Access the Application
*   **Web App:** [http://localhost:3000](http://localhost:3000)
*   **Backend API Swagger Docs:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 📂 Project Structure

```text
veetrack-f1/
├── package.json           # Root scripts (npm run fresh, setup:win)
├── requirements.txt       # Unified Python dependencies
├── .env                   # Environment variables
├── veetrack-backend/      # Python FastAPI Microservice
│   ├── main.py            # API Entry Point
│   ├── routers/           # API endpoints (intelligence, chat, feed)
│   ├── services/          # Business logic & ML pipelines
│   └── tasks/             # Celery background workers
├── veetrack-frontend/     # Vite React SPA Web App
│   ├── index.html         # Main entrypoint
│   ├── vite.config.js     # Vite bundler config
│   ├── src/               # React JSX source files
│   └── src/components/    # Reusable UI components
└── scripts/               # Helper bash and batch scripts for Windows/Linux
```

---

*Built with ❤️ by Vee Technologies.*
