@echo off
REM Unified Healthcare System Startup Script
REM This script checks prerequisites and starts the system

echo ============================================================
echo   Unified Healthcare System - Startup Script
echo ============================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python 3.8+ and try again
    pause
    exit /b 1
)

echo [OK] Python found
python --version
echo.

REM Check if virtual environment exists (optional)
if exist "derja\Scripts\activate.bat" (
    echo [INFO] Activating virtual environment...
    call derja\Scripts\activate.bat
    echo.
)

REM Check if requirements are installed
echo [CHECK] Verifying dependencies...
python -c "import spacy, flask, fastapi, sentence_transformers, faiss" >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Some dependencies may be missing
    echo [INFO] Installing requirements...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install requirements
        pause
        exit /b 1
    )
    echo [OK] Dependencies installed
    echo.
) else (
    echo [OK] Dependencies verified
    echo.
)

REM Check if NER model exists
if not exist "models\symptom_ner_spacy\config.cfg" (
    echo [WARNING] NER model not found
    echo [INFO] Training NER model (this may take a few minutes)...
    python src\train_ner.py
    if errorlevel 1 (
        echo [ERROR] Failed to train NER model
        echo [WARNING] Continuing anyway - symptom extraction may not work
        echo.
    ) else (
        echo [OK] NER model trained
        echo.
    )
) else (
    echo [OK] NER model found
    echo.
)

REM Check if FAISS indices exist
if not exist "diag\full_medical_index.faiss" (
    echo [WARNING] FAISS indices not found
    echo [INFO] Building FAISS indices (this may take a few minutes)...
    echo [INFO] Checking if nhs_conditions2.json exists...
    if not exist "diag\nhs_conditions2.json" (
        echo [ERROR] nhs_conditions2.json not found in diag folder
        echo [ERROR] Please ensure the file exists before building indices
        pause
        exit /b 1
    )
    cd diag
    python embedding.py
    if errorlevel 1 (
        echo [ERROR] Failed to build FAISS indices
        echo [WARNING] Continuing anyway - diagnosis may not work
        cd ..
        echo.
    ) else (
        echo [OK] FAISS indices built
        cd ..
        echo.
    )
) else (
    echo [OK] FAISS indices found
    echo.
)

REM Check if retrival.py metadata exists
if not exist "diag\full_medical_metadata.pkl" (
    echo [WARNING] Medical metadata not found
    echo [INFO] Building metadata files...
    cd diag
    python embedding.py
    cd ..
    echo.
)

REM Start the unified healthcare server
echo ============================================================
echo   Starting Unified Healthcare System...
echo ============================================================
echo.
echo [INFO] API Server will run on: http://localhost:5000
echo [INFO] Web UI will open at: http://localhost:8000/unified_healthcare_ui.html
echo.
echo Press Ctrl+C to stop the servers
echo.

python unified_healthcare_server.py

pause

