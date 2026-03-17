# AI Service Python Environment

## Recommended Python Version

Use **Python 3.12.x** (or 3.11.x) for local development of the AI service.

Reason: `PyMuPDF==1.23.7` from `ai-service/requirements.txt` can fail to install on Python 3.14 on Windows.

## Quick Setup (Windows PowerShell)

```powershell
cd ai-service
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pytest tests/ -v
```

## If You Are Already on Python 3.14

Some dependencies might fail during full installation (notably PyMuPDF).

For running current tests locally in this repository, these packages were required:

```powershell
python -m pip install dateparser pytesseract rapidfuzz pydantic-settings pydantic opencv-python-headless
```

This workaround is useful for test validation, but Python 3.12 is still the recommended baseline.