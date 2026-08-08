# IoT Sensor Monitor (minimal)

This is a minimal web-based IoT sensor monitor using FastAPI, WebSocket, and SQLite.


Run locally with Python (optional):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Run with Docker (recommended):

```bash
docker compose up --build
```

Open http://localhost:8000/
