# app\workers\worker.py
# app/workers/worker.py
import asyncio
import logging
import subprocess
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass

from opentelemetry import trace
from opentelemetry.propagate import extract
import pgf  # The GF Python bindings

from app.shared.config import settings, StorageBackend
from app.shared.telemetry import setup_telemetry, get_tracer
from app.adapters.s3_repo import S3LanguageRepo

logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)

# --- Lazy Singleton Runtime (Phase 2) ---
@dataclass
class GrammarRuntime:
    """
    Singleton that holds loaded PGF binaries in memory.
    Prevents 'Cold Start' latency for validation/generation tasks.
    """
    _pgf: Optional[pgf.PGF] = None
    
    def load(self, pgf_path: str):
        logger.info(f"Loading PGF binary from {pgf_path} into RAM...")
        if os.path.exists(pgf_path):
            self._pgf = pgf.readPGF(pgf_path)
            logger.info("PGF Loaded successfully.")
        else:
            logger.warning(f"PGF not found at {pgf_path}. Runtime is empty.")

    def get(self) -> Optional[pgf.PGF]:
        return self._pgf

# Global Instance
runtime = GrammarRuntime()

# --- Job Logic ---

async def compile_grammar(ctx: Dict[str, Any], language_code: str, trace_context: Dict[str, str] = None) -> str:
    """
    ARQ Job: Compiles a GF source file into a PGF binary.
    """
    # 1. Link Telemetry Span
    if trace_context:
        ctx_otel = extract(trace_context)
    else:
        ctx_otel = None

    with tracer.start_as_current_span("worker_compile_grammar", context=ctx_otel) as span:
        span.set_attribute("language.code", language_code)
        
        try:
            logger.info(f"Starting compilation for {language_code}...")
            
            # 2. Define Paths
            # Assuming standard RGL structure: src/finnish/Finnish.gf
            # In a real app, these paths would be dynamic based on the Language domain model
            src_dir = f"{settings.FILESYSTEM_REPO_PATH}/src"
            target_pgf = f"{settings.FILESYSTEM_REPO_PATH}/build/{language_code}.pgf"
            
            # Ensure build dir exists
            os.makedirs(os.path.dirname(target_pgf), exist_ok=True)

            # 3. Execute GF Compiler (CPU Intensive)
            # cmd: gf -make -output-format=pgf src/Language.gf
            cmd = [
                "gf", 
                "-make", 
                "--output-format=pgf",
                f"{src_dir}/{language_code}.gf"  # Simplified entry point
            ]
            
            # Run in thread pool to avoid blocking the asyncio loop
            process = await asyncio.to_thread(
                subprocess.run, 
                cmd, 
                capture_output=True, 
                text=True
            )

            if process.returncode != 0:
                raise RuntimeError(f"GF Compilation Failed: {process.stderr}")

            logger.info(f"Compilation successful: {target_pgf}")
            span.add_event("compilation_complete")

            # 4. Persistence (Phase 2 Requirement)
            # If S3 is enabled, upload the artifact.
            if settings.STORAGE_BACKEND == StorageBackend.S3:
                repo = S3LanguageRepo()
                with open(target_pgf, "rb") as f:
                    content = f.read()
                    await repo.save_pgf(language_code, content)
                span.add_event("upload_to_s3_complete")

            # 5. Hot Reload (Lazy Singleton Update)
            # Update the resident memory model so subsequent checks are fast
            runtime.load(target_pgf)
            
            return f"Compiled {language_code} successfully."

        except Exception as e:
            logger.error(f"Job failed: {e}")
            span.record_exception(e)
            raise e

# --- ARQ Worker Configuration ---

async def startup(ctx):
    """
    Lifecycle Hook: Runs when the Worker Container starts.
    """
    setup_telemetry("architect-worker")
    logger.info("Worker started. Telemetry initialized.")
    
    # Pre-warm: If a default grammar exists, load it now.
    default_pgf = f"{settings.FILESYSTEM_REPO_PATH}/build/AbstractWiki.pgf"
    if os.path.exists(default_pgf):
        runtime.load(default_pgf)

async def shutdown(ctx):
    logger.info("Worker shutting down...")

class WorkerSettings:
    """
    ARQ Configuration Class.
    """
    redis_settings = settings.redis_url
    functions = [compile_grammar]
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = settings.WORKER_CONCURRENCY
    # DLQ (Dead Letter Queue) logic would be configured here if strictly required
    # handle_signals = False