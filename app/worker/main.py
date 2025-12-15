# app\worker\main.py
import asyncio
import signal
import structlog
from app.shared.container import container
from app.shared.config import settings
from app.core.domain.events import EventType
from app.worker.tasks import BuildTaskHandler

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.JSONRenderer()
    ]
)
logger = structlog.get_logger()

async def shutdown(loop, signal=None):
    """Cleanup tasks tied to the service's shutdown."""
    if signal:
        logger.info(f"Received exit signal {signal.name}...")
    
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    
    logger.info(f"Cancelling {len(tasks)} outstanding tasks")
    [task.cancel() for task in tasks]

    await asyncio.gather(*tasks, return_exceptions=True)
    
    # Close Broker Connection
    broker = container.message_broker()
    await broker.disconnect()
    
    loop.stop()

async def main():
    logger.info("worker_startup", env=settings.ENV)

    # 1. Wire Dependencies
    # The tasks module uses @inject, so we must wire it.
    container.wire(modules=[
        "app.worker.tasks"
    ])

    # 2. Infrastructure Setup
    broker = container.message_broker()
    await broker.connect()

    # 3. Register Event Handlers
    # We instantiate the handler (dependencies injected automatically via @inject)
    build_handler = BuildTaskHandler()
    
    await broker.subscribe(
        EventType.BUILD_REQUESTED,
        build_handler.handle
    )
    
    logger.info("worker_ready_listening")

    # 4. Keep Alive
    # The broker's listener loop runs in the background. 
    # We need this main coroutine to stay alive.
    try:
        # We wait on a future that never completes, unless cancelled
        await asyncio.Future()
    except asyncio.CancelledError:
        logger.info("worker_main_cancelled")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Graceful Shutdown Handling
    signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
    for s in signals:
        loop.add_signal_handler(
            s, lambda s=s: asyncio.create_task(shutdown(loop, s))
        )

    try:
        loop.run_until_complete(main())
    finally:
        loop.close()
        logger.info("worker_shutdown_complete")