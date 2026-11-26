"""
Root-level shim for agentcore dev.

agentcore dev expects to import 'app:app' from the working directory.
This file re-exports the real app from src/agentcore/app.py.
"""

from src.agentcore.app import app, invoke  # noqa: F401
