# Unified Healthcare System Startup Script (PowerShell)
# This script checks prerequisites and starts the system

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Unified Healthcare System - Startup Script" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Check if Python is installed
try {
    $pythonVersion = python --version 2>&1
    Write-Host "[OK] Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Please install Python 3.8+ and try again" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""

# Check if virtual environment exists (optional)
if (Test-Path "derja\Scripts\Activate.ps1") {
    Write-Host "[INFO] Activating virtual environment..." -ForegroundColor Yellow
    & "derja\Scripts\Activate.ps1"
    Write-Host ""
}

# Check if requirements are installed
Write-Host "[CHECK] Verifying dependencies..." -ForegroundColor Yellow
try {
    python -c "import spacy, flask, fastapi, sentence_transformers, faiss" 2>&1 | Out-Null
    Write-Host "[OK] Dependencies verified" -ForegroundColor Green
} catch {
    Write-Host "[WARNING] Some dependencies may be missing" -ForegroundColor Yellow
    Write-Host "[INFO] Installing requirements..." -ForegroundColor Yellow
    pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Failed to install requirements" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    Write-Host "[OK] Dependencies installed" -ForegroundColor Green
}
Write-Host ""

# Check if NER model exists
if (-not (Test-Path "models\symptom_ner_spacy\config.cfg")) {
    Write-Host "[WARNING] NER model not found" -ForegroundColor Yellow
    Write-Host "[INFO] Training NER model (this may take a few minutes)..." -ForegroundColor Yellow
    python src\train_ner.py
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Failed to train NER model" -ForegroundColor Red
        Write-Host "[WARNING] Continuing anyway - symptom extraction may not work" -ForegroundColor Yellow
    } else {
        Write-Host "[OK] NER model trained" -ForegroundColor Green
    }
    Write-Host ""
} else {
    Write-Host "[OK] NER model found" -ForegroundColor Green
    Write-Host ""
}

# Check if FAISS indices exist
if (-not (Test-Path "diag\full_medical_index.faiss")) {
    Write-Host "[WARNING] FAISS indices not found" -ForegroundColor Yellow
    Write-Host "[INFO] Building FAISS indices (this may take a few minutes)..." -ForegroundColor Yellow
    Push-Location diag
    python embedding.py
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Failed to build FAISS indices" -ForegroundColor Red
        Write-Host "[WARNING] Continuing anyway - diagnosis may not work" -ForegroundColor Yellow
    } else {
        Write-Host "[OK] FAISS indices built" -ForegroundColor Green
    }
    Pop-Location
    Write-Host ""
} else {
    Write-Host "[OK] FAISS indices found" -ForegroundColor Green
    Write-Host ""
}

# Check if retrival.py metadata exists
if (-not (Test-Path "diag\full_medical_metadata.pkl")) {
    Write-Host "[WARNING] Medical metadata not found" -ForegroundColor Yellow
    Write-Host "[INFO] Building metadata files..." -ForegroundColor Yellow
    Push-Location diag
    python embedding.py
    Pop-Location
    Write-Host ""
}

# Start the unified healthcare server
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Starting Unified Healthcare System..." -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "[INFO] API Server will run on: http://localhost:5000" -ForegroundColor Yellow
Write-Host "[INFO] Web UI will open at: http://localhost:8000/unified_healthcare_ui.html" -ForegroundColor Yellow
Write-Host ""
Write-Host "Press Ctrl+C to stop the servers" -ForegroundColor Yellow
Write-Host ""

python unified_healthcare_server.py

Read-Host "Press Enter to exit"

