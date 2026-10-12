#!/bin/bash
# Backend on 8000 (internal), Streamlit on 7860 (public)
(cd "$(dirname "$0")/backend" && uvicorn main:app --host 127.0.0.1 --port 8000) &
cd "$(dirname "$0")/frontend" && exec streamlit run app.py --server.port 7860 --server.address 0.0.0.0 \
  --server.headless true --server.enableCORS false --server.enableXsrfProtection false
