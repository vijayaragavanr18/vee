$ErrorActionPreference = "Stop"
Write-Host "Initializing VeeTrack Native Dev Mode..." -ForegroundColor Green

# 1. Create and activate virtual environment if it doesn't exist
if (-not (Test-Path "venv")) {
    Write-Host "Creating Python virtual environment..."
    python -m venv venv
}

# Source venv
.\venv\Scripts\Activate.ps1

# 2. Install dependencies
Write-Host "Installing pip requirements..."
pip install -r requirements.txt

# 3. Change directory to backend
cd veetrack-backend

# 4. Generate SQLite Migration
Write-Host "Running Alembic Database Migrations..."
# We use revision --autogenerate to create the initial tables in sqlite, 
# then upgrade head. Since this is a new DB file.
alembic upgrade head
if ($LASTEXITCODE -ne 0) {
    # If head upgrade fails (meaning no migration exists or initial db is empty), 
    # generate a fresh one and upgrade.
    alembic revision --autogenerate -m "Initial sqlite schema"
    alembic upgrade head
}

# 5. Boot Uvicorn
Write-Host "Booting FastAPI Server on port 8000..." -ForegroundColor Cyan
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
