# app\core\__init__.py
"""
Core Domain Layer.

This package contains the pure business logic and entities of the system.
It strictly follows the Hexagonal Architecture (Ports & Adapters) pattern:
- No dependencies on frameworks (FastAPI, Flask, Django).
- No dependencies on infrastructure (Database, Redis, FileSystem).
- Defines Interfaces (Ports) that the Infrastructure layer must implement.
"""