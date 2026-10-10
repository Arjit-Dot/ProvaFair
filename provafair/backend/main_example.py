"""Minimal entry point. If you already have a main.py, just add the two api_v2 lines."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import api_v2

app = FastAPI(title="ProvaFair")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(api_v2.router)
