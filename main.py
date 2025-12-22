"""
Root entrypoint for Railway / Docker.

This file intentionally forwards execution to the real app:
backend.app.main:app

DO NOT add routes here.
DO NOT duplicate logic here.
"""

from backend.app.main import app  # noqa: F401
