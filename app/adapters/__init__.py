# app\adapters\__init__.py
"""
Infrastructure Adapters.

This package contains the concrete implementations of the Ports defined in `app.core.ports`.
These adapters connect the application to the outside world:
- `api`: The Primary Adapter (Driving) - FastAPI web server.
- `filesystem`: Secondary Adapter (Driven) - Local file storage.
- `gf_runtime`: Secondary Adapter (Driven) - The GF binary wrapper.
- `redis_broker`: Secondary Adapter (Driven) - Async messaging.

In Hexagonal Architecture, dependencies point INWARD. These modules depend on `app.core`,
but `app.core` never imports from here.
"""