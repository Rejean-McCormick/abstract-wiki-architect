# app\worker\__init__.py
"""
Background Worker Application.

This package contains the entry point and logic for the background worker service.
The worker acts as a Driving Adapter that:
1. Listens to domain events via the Message Broker (Redis).
2. Executes long-running tasks (e.g., Language Compilation) using the Core Domain.

Components:
- main: The entry point script that initializes the container and starts the listening loop.
"""

from .main import run_worker

__all__ = ["run_worker"]