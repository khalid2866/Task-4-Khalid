@echo off
REM Quick launcher for the Intelligent Code Reviewer & Explainer (Windows).
cd /d "%~dp0"

if not exist venv (
  echo Creating virtual environment...
  python -m venv venv
)
call venv\Scripts\activate.bat
pip install -q -r requirements.txt

echo.
echo === Demo: reviewing samples\buggy_example.py (offline engine) ===
python -m reviewer review samples\buggy_example.py
echo.
echo Tip: python -m reviewer review ^<your-file^> --engine gemini --save
echo      Web UI: python web\app.py  -^>  http://127.0.0.1:5054
