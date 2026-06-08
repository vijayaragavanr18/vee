@echo off
setlocal
echo === VeeTrack One-Time Setup (Windows) ===
echo.

echo [1/4] Checking Database / Cache...
echo Using SQLite and DiskCache natively. No Redis required ✓
echo.

echo [2/4] Checking Ollama...
echo Ensure Ollama for Windows is installed from https://ollama.com/download
ollama list 2>nul | findstr "llama3.2:1b" >nul
if %ERRORLEVEL% NEQ 0 (
    echo Please load your custom llama3.2:1b model.
) else (
    echo Ollama + llama3.2:1b [OK]
)
echo.

echo [3/4] Setting up Python environment...
cd ..\veetrack-backend
if not exist venv (
    python -m venv venv
)
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r ..\requirements.txt
python -m spacy download en_core_web_trf || python -m spacy download en_core_web_sm
python -c "import nltk; nltk.download('punkt', quiet=True); nltk.download('punkt_tab', quiet=True); nltk.download('stopwords', quiet=True)"
echo Python environment [OK]
echo.

echo [4/4] Setting up frontend...
cd ..\veetrack-frontend
call npm install
echo Frontend [OK]
echo.

echo === Setup complete! ===
echo Start the app with: npm run dev:all
cd ..
