# app/workers/worker.py
import asyncio
import os
import sys
import subprocess
import structlog
from dataclasses import dataclass
from typing import Dict, Any, Optional

# Add project root to path for reliable imports
sys.path.append(os.getcwd())

from arq.connections import RedisSettings
from opentelemetry.propagate import extract

# v2.0 Optimization: OS-Native File Watching
try:
    from watchfiles import awatch
except ImportError:
    awatch = None

try:
    import pgf
except ImportError:
    pgf = None

from app.shared.config import settings, StorageBackend
from app.shared.telemetry import setup_telemetry, get_tracer

# Conditional Import for S3
try:
    from app.adapters.s3_repo import S3LanguageRepo
except ImportError:
    S3LanguageRepo = None

logger = structlog.get_logger()
tracer = get_tracer(__name__)

# --- Lazy Singleton Runtime ---
@dataclass
class GrammarRuntime:
    """
    Singleton that holds loaded PGF binaries in memory.
    Prevents 'Cold Start' latency for validation/generation tasks.
    """
    _pgf: Optional[Any] = None
    _last_mtime: float = 0.0
    
    def load(self, pgf_path: str):
        logger.info("runtime_loading_pgf", path=pgf_path)
        if pgf and os.path.exists(pgf_path):
            try:
                # Update mtime tracking
                self._last_mtime = os.path.getmtime(pgf_path)
                self._pgf = pgf.readPGF(pgf_path)
                logger.info("runtime_pgf_loaded_success", languages=list(self._pgf.languages.keys()))
            except Exception as e:
                logger.error("runtime_pgf_load_failed", error=str(e))
        else:
            logger.warning("runtime_pgf_not_found_or_no_lib", path=pgf_path)

    def get(self) -> Optional[Any]:
        return self._pgf

    async def reload(self):
        """Helper to reload the current configured path."""
        logger.info("runtime_reloading_triggered")
        self.load(settings.AW_PGF_PATH)

# Global Instance
runtime = GrammarRuntime()

# --- Job Logic ---

async def compile_grammar(ctx: Dict[str, Any], language_code: str, trace_context: Dict[str, str] = None) -> str:
    """
    ARQ Job: Compiles a single GF source file (Tier 2/3 dev mode).
    Note: Production builds are handled by build_orchestrator.py.
    """
    # 1. Link Telemetry Span (Distributed Tracing)
    ctx_otel = extract(trace_context) if trace_context else None

    with tracer.start_as_current_span("worker_compile_grammar", context=ctx_otel) as span:
        span.set_attribute("language.code", language_code)
        
        try:
            logger.info("compilation_started", lang=language_code)
            
            # 2. Define Paths
            base_dir = settings.FILESYSTEM_REPO_PATH
            src_file = os.path.join(base_dir, "gf", f"Wiki{language_code.capitalize()}.gf")
            
            # 3. Execute GF Compiler
            cmd = [
                "gf", 
                "-batch",
                "-make", 
                "--output-format=pgf", 
                src_file
            ]
            
            if os.path.exists(src_file):
                logger.info("executing_subprocess", cmd=" ".join(cmd))
                
                process = await asyncio.to_thread(
                    subprocess.run, 
                    cmd, 
                    capture_output=True, 
                    text=True,
                    cwd=os.path.join(base_dir, "gf")
                )

                if process.returncode != 0:
                    error_msg = f"GF Compilation Failed: {process.stderr}"
                    logger.error("compilation_failed", error=error_msg)
                    raise RuntimeError(error_msg)
                
                logger.info("subprocess_success", output=process.stdout[:100])
            else:
                logger.warning("source_file_missing", path=src_file)
                return "Source file missing"

            # 4. Persistence (S3)
            if settings.STORAGE_BACKEND == StorageBackend.S3 and S3LanguageRepo:
                target_pgf = settings.AW_PGF_PATH
                if os.path.exists(target_pgf):
                    repo = S3LanguageRepo()
                    with open(target_pgf, "rb") as f:
                        content = f.read()
                        await repo.save_grammar(language_code, content)
                    logger.info("s3_upload_success", bucket=settings.AWS_BUCKET_NAME)
                else:
                    logger.warning("s3_upload_skipped", msg="PGF file not found locally")

            # 5. Hot Reload
            if os.path.exists(settings.AW_PGF_PATH):
                await runtime.reload()
            
            logger.info("compilation_complete", lang=language_code)
            return f"Compiled {language_code} successfully."

        except Exception as e:
            logger.error("job_failed", error=str(e))
            span.record_exception(e)
            raise e

# --- Background Tasks ---

async def watch_grammar_file(ctx):
    """
    Background Task: Watches the PGF binary for changes.
    Optimized: Uses 'watchfiles' (OS events) if available, falls back to polling.
    """
    pgf_path = settings.AW_PGF_PATH
    pgf_dir = os.path.dirname(pgf_path)
    
    # Ensure directory exists to watch
    if not os.path.exists(pgf_dir):
        logger.warning("watcher_dir_missing", path=pgf_dir)
        return

    logger.info("watcher_started", path=pgf_path, mechanism="watchfiles" if awatch else "polling")

    if awatch:
        try:
            # 🚀 v2.0: OS-Native Event Loop
            # This triggers instantly when build_orchestrator.py atomic move completes
            async for changes in awatch(pgf_dir):
                for change_type, file_path in changes:
                    if os.path.abspath(file_path) == os.path.abspath(pgf_path):
                        logger.info("watcher_detected_change", file=file_path, type=change_type)
                        # Small yield to ensure file handle is free
                        await asyncio.sleep(0.1)
                        runtime.load(pgf_path)
        except Exception as e:
            logger.error("watcher_crashed", error=str(e))
    else:
        # Fallback: Polling Loop (Legacy)
        while True:
            try:
                current_mtime = 0
                if os.path.exists(pgf_path):
                    current_mtime = os.path.getmtime(pgf_path)
                
                if current_mtime > runtime._last_mtime:
                    logger.info("watcher_polling_change", old=runtime._last_mtime, new=current_mtime)
                    runtime.load(pgf_path)
                
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                logger.info("watcher_stopped")
                break
            except Exception as e:
                logger.error("watcher_error", error=str(e))
                await asyncio.sleep(10)

# --- ARQ Worker Configuration ---

async def startup(ctx):
    """Lifecycle Hook: Runs when the Worker Container starts."""
    setup_telemetry("architect-worker")
    logger.info("worker_startup", queue=settings.REDIS_QUEUE_NAME)
    
    # 1. Initial Load
    runtime.load(settings.AW_PGF_PATH)

    # 2. Start Background Watcher
    ctx['watcher_task'] = asyncio.create_task(watch_grammar_file(ctx))

async def shutdown(ctx):
    logger.info("worker_shutdown")
    if 'watcher_task' in ctx:
        ctx['watcher_task'].cancel()
        await ctx['watcher_task']

class WorkerSettings:
    """
    ARQ Configuration Class.
    """
    # 🩹 FIX: Use REDIS_URL for v2.0 Architecture
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)

    queue_name = settings.REDIS_QUEUE_NAME
    functions = [compile_grammar]
    
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = settings.WORKER_CONCURRENCY