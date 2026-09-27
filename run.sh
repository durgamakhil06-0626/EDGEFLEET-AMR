#!/bin/bash
cd "$(dirname "$0")"
python3 -m pip install -r backend/requirements.txt
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
