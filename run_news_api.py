#!/usr/bin/env python3
"""Run the Transparent News Assistant API server."""
import uvicorn  # type: ignore[import-untyped]
from news_assistant.api import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
