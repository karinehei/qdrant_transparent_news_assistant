# Scripts Directory

This directory contains utility scripts and tools for the project.

## Structure

- **`run_news_api.py`** - Entry point for running the API server locally
- **`tools.py`** - CLI tool for indexing, searching, and managing the RAG pipeline
- **`demo.sh`** - Demo script for testing the system
- **`make.ps1`**, **`Makefile.ps1`** - PowerShell versions of Makefile commands
- **`fix_docker_creds.ps1`**, **`fix_docker_creds.sh`** - Scripts to fix Docker credential issues

## Legacy Scripts

The `legacy/` subdirectory contains older demo and reference scripts:
- `mini_rag_pipeline_qdrant.py` - Original mini RAG pipeline demo
- `document_processing.py` - Document processing utilities
- `indexing.py` - Indexing utilities
- `retrieval.py` - Retrieval utilities (note: active version is in `news_assistant/retrieval.py`)
- `prompting.py` - Prompting utilities
- `config.py` - Old configuration file (replaced by `news_assistant/settings.py`)

These legacy scripts are kept for reference but are not actively used in the current implementation.
