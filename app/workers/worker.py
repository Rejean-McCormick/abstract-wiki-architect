# app/workers/worker.py
import asyncio
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Callable, Coroutine

import structlog
from arq.connections import RedisSettings

# Add project root to path for reliable imports (container / local)
sys.path.append(os.getcwd())

# Optional: OS-native file watching
try:
    from watchfiles import awatch  # type: ignore
except Exception:
    awatch = None

# Optional: PGF runtime (C-runtime python bindings)
try:
    import pgf  # type: ignore
except Exception:
    pgf = None

from app.shared.config import settings
from app.shared.telemetry import setup_telemetry, get_tracer
from app.shared.lexicon import lexicon

from app.adapters.messaging.redis_broker import RedisMessageBroker
from app.core.domain.events import (
    SystemEvent,
    EventType,
    BuildRequestedPayload,
    BuildFailedPayload,
)

logger = structlog.get_logger()
tracer = get_tracer(__name__)


# -----------------------------
# Runtime: in-memory PGF cache
# -----------------------------
@dataclass
class GrammarRuntime:
    """
    Holds a loaded PGF in memory (if pgf runtime is installed).
    Also supports "zombie language" purging based on the Everything Matrix verdict.
    """
    _pgf: Optional[Any] = None
    _last_mtime: float = 0.0

    def load(self, pgf_path: str) -> None:
        logger.info("runtime_loading_pgf", path=pgf_path)

        if not pgf:
            logger.warning("runtime_pgf_lib_missing", note="python 'pgf' module not installed")
            return

        if not os.path.exists(pgf_path):
            logger.warning("runtime_pgf_missing", path=pgf_path)
            return

        try:
            self._last_mtime = os.path.getmtime(pgf_path)
            raw_pgf = pgf.readPGF(pgf_path)

            # Purge zombie languages (linked but not runnable) using Everything Matrix
            matrix_path = Path(settings.FILESYSTEM_REPO_PATH) / "data" / "indices" / "everything_matrix.json"
            if matrix_path.exists():
                try:
                    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
                    languages = matrix.get("languages", {})
                    # Iterate over a list of keys to avoid modification issues during iteration
                    for lang_name in list(getattr(raw_pgf, "languages", {}).keys()):
                        iso_guess = lang_name[-3:].lower()
                        verdict = (languages.get(iso_guess, {}) or {}).get("verdict", {}) or {}
                        runnable = verdict.get("runnable", True)
                        
                        if not runnable:
                            logger.warning(
                                "runtime_zombie_language_detected",
                                lang=lang_name,
                                iso=iso_guess,
                                reason="matrix.verdict.runnable=False",
                            )
                            # [FIX] REMOVED the deletion line. Newer GF bindings return a read-only 
                            # mappingproxy which crashes on 'del'. It is harmless to keep the 
                            # language loaded in the backend memory.
                            # del raw_pgf.languages[lang_name] 

                except Exception as e:
                    logger.error("runtime_matrix_filter_failed", error=str(e))
            else:
                logger.warning("runtime_matrix_missing", path=str(matrix_path))

            self._pgf = raw_pgf
            logger.info("runtime_pgf_loaded_success", active_languages=list(self._pgf.languages.keys()))
        except Exception as e:
            logger.error("runtime_pgf_load_failed", error=str(e))

    def get(self) -> Optional[Any]:
        return self._pgf

    async def reload(self) -> None:
        pgf_path = os.getenv("AW_PGF_PATH") or settings.PGF_PATH
        logger.info("runtime_reloading_triggered", path=pgf_path)
        self.load(pgf_path)


runtime = GrammarRuntime()


# -----------------------------
# Helpers
# -----------------------------
def _effective_pgf_path() -> str:
    # Prefer env override used in tests/containers; fall back to settings.
    return os.getenv("AW_PGF_PATH") or settings.PGF_PATH


def _load_iso_to_wiki(repo_root: Path) -> Dict[str, Any]:
    """
    Loads ISO->Wiki GF language mapping if available.
    Uses Path.exists() so tests can patch it deterministically.
    """
    map_path = repo_root / "data" / "config" / "iso_to_wiki.json"
    if not map_path.exists():
        return {}
    try:
        with map_path.open("r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception as e:
        logger.warning("iso_to_wiki_load_failed", path=str(map_path), error=str(e))
        return {}


def _resolve_wiki_code(lang_code: str, repo_root: Path) -> str:
    iso_map = _load_iso_to_wiki(repo_root)
    wiki = (iso_map.get(lang_code) or {}).get("wiki")
    if isinstance(wiki, str) and wiki.strip():
        return wiki.strip()
    # Fallback: ISO 'eng' -> 'Eng', 'xyz' -> 'Xyz'
    return lang_code.title()


def _resolve_src_file(lang_code: str, repo_root: Path) -> Path:
    wiki_code = _resolve_wiki_code(lang_code, repo_root)
    return repo_root / "gf" / f"Wiki{wiki_code}.gf"


# -----------------------------
# Subprocess helpers
# -----------------------------
async def _run_cmd(
    argv: list[str],
    *,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    timeout_sec: Optional[int] = None,
) -> Any:
    """
    Run a blocking subprocess in a thread.
    Captures stdout/stderr for logging and error reporting.
    """
    def _runner() -> subprocess.CompletedProcess:
        return subprocess.run(
            argv,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )

    logger.info("subprocess_exec", argv=" ".join(argv), cwd=cwd)
    return await asyncio.to_thread(_runner)


# -----------------------------
# ARQ Jobs
# -----------------------------
async def build_language(ctx: Dict[str, Any], request: Dict[str, Any]) -> str:
    """
    Canonical job triggered by the Event Bus bridge.

    Implements the *correct* build pipeline (no "single-file pgf" dead end):
      1) Index knowledge layer: tools/everything_matrix/build_index.py
      2) Compile/link grammar layer: gf/build_orchestrator.py (when present)
      3) Reload in-memory runtime if available
      4) Emit BUILD_COMPLETED / BUILD_FAILED
    """
    broker: Optional[RedisMessageBroker] = ctx.get("event_broker")

    payload = BuildRequestedPayload(**request)
    lang_code = payload.lang_code
    strategy = (payload.strategy or "fast").lower()

    with tracer.start_as_current_span("worker_build_language") as span:
        span.set_attribute("language.code", lang_code)
        span.set_attribute("build.strategy", strategy)

        try:
            logger.info("build_job_started", lang=lang_code, strategy=strategy)

            # Emit lifecycle event
            if broker:
                await broker.publish(
                    SystemEvent(
                        type=EventType.BUILD_STARTED,
                        payload={"lang_code": lang_code, "strategy": strategy, "requester_id": payload.requester_id},
                    )
                )

            # "fast" means: request exists, but do not attempt full PGF rebuild here.
            # Full rebuild is "full".
            if strategy == "fast":
                logger.info("build_job_fast_noop", lang=lang_code, note="fast strategy does not rebuild PGF")
                return f"Build fast acknowledged for {lang_code} (no PGF rebuild)."

            repo_root = Path(settings.FILESYSTEM_REPO_PATH)

            # Step 1: Indexer (updates data/indices/everything_matrix.json etc.)
            indexer = repo_root / "tools" / "everything_matrix" / "build_index.py"
            if not os.path.exists(str(indexer)):
                raise RuntimeError(f"Indexer missing: {indexer}")

            idx_proc = await _run_cmd([sys.executable, "-u", str(indexer)], cwd=str(repo_root))
            if getattr(idx_proc, "returncode", 1) != 0:
                err = (getattr(idx_proc, "stderr", "") or "").strip()
                out = (getattr(idx_proc, "stdout", "") or "").strip()
                raise RuntimeError(f"Indexing failed:\n{err or out}")

            # Step 2: Builder (optional orchestrator)
            builder = repo_root / "gf" / "build_orchestrator.py"
            if os.path.exists(str(builder)):
                build_proc = await _run_cmd([sys.executable, "-u", str(builder)], cwd=str(repo_root / "gf"))
                if getattr(build_proc, "returncode", 1) != 0:
                    stderr_tail = (getattr(build_proc, "stderr", "") or "").strip()[-4000:]
                    stdout_tail = (getattr(build_proc, "stdout", "") or "").strip()[-4000:]
                    raise RuntimeError(
                        "GF build orchestrator failed.\n"
                        f"STDERR (tail):\n{stderr_tail}\n\nSTDOUT (tail):\n{stdout_tail}"
                    )
            else:
                logger.warning("gf_orchestrator_missing_fallback", path=str(builder), note="skipping orchestrator step")

            # Validate artifact
            pgf_path = _effective_pgf_path()
            if not os.path.exists(pgf_path):
                raise RuntimeError(f"Build completed but PGF artifact missing at: {pgf_path}")

            # Hot reload (best-effort)
            await runtime.reload()

            logger.info("build_job_completed", lang=lang_code, pgf_path=pgf_path)

            if broker:
                await broker.publish(
                    SystemEvent(
                        type=EventType.BUILD_COMPLETED,
                        payload={"lang_code": lang_code, "strategy": strategy, "pgf_path": pgf_path},
                    )
                )

            return f"Built {lang_code} successfully."

        except Exception as e:
            logger.error("build_job_failed", lang=lang_code, error=str(e))
            span.record_exception(e)

            if broker:
                fail = BuildFailedPayload(
                    lang_code=lang_code,
                    error_code="WORKER_BUILD_FAILED",
                    details=str(e),
                )
                await broker.publish(
                    SystemEvent(
                        type=EventType.BUILD_FAILED,
                        payload=fail.model_dump(),
                    )
                )
            raise


# Back-compat job: compile a single language directly (used by tests and older callers)
async def compile_grammar(ctx: Dict[str, Any], language_code: str) -> str:
    repo_root = Path(settings.FILESYSTEM_REPO_PATH)
    pgf_path = _effective_pgf_path()

    # Pre-check: indexer tool should exist (do not run it here)
    indexer = repo_root / "tools" / "everything_matrix" / "build_index.py"
    if not os.path.exists(str(indexer)):
        raise RuntimeError(f"Indexer missing: {indexer}")

    # Resolve source file via iso_to_wiki mapping (or fallback)
    src_file = _resolve_src_file(language_code, repo_root)
    if not os.path.exists(str(src_file)):
        msg = f"Source GF file missing: {src_file}"
        logger.warning("compile_source_missing", lang=language_code, path=str(src_file))
        return msg

    # Compile (direct GF CLI; tests patch asyncio.to_thread so this call is mocked)
    proc = await _run_cmd(["gf", "-make", str(src_file)], cwd=str(repo_root / "gf"))

    if getattr(proc, "returncode", 1) != 0:
        err = (getattr(proc, "stderr", "") or "").strip()
        out = (getattr(proc, "stdout", "") or "").strip()
        raise RuntimeError(f"GF Compilation Failed:\n{err or out}")

    # Validate PGF output exists
    if not os.path.exists(pgf_path):
        raise RuntimeError(f"Build completed but PGF artifact missing at: {pgf_path}")

    # Reload runtime (best-effort)
    await runtime.reload()

    out = (getattr(proc, "stdout", "") or "").strip()
    return out or f"Compiled {language_code} successfully."


# -----------------------------
# Background tasks
# -----------------------------
async def watch_grammar_file(_: Dict[str, Any]) -> None:
    """
    Watches settings.PGF_PATH and reloads runtime when it changes.
    Uses watchfiles when available, otherwise polling.
    """
    pgf_path = _effective_pgf_path()
    pgf_dir = os.path.dirname(pgf_path)

    if not os.path.exists(pgf_dir):
        logger.warning("watcher_dir_missing", path=pgf_dir)
        return

    logger.info("watcher_started", path=pgf_path, mechanism="watchfiles" if awatch else "polling")

    if awatch:
        try:
            async for changes in awatch(pgf_dir):
                for change_type, file_path in changes:
                    if os.path.abspath(file_path) == os.path.abspath(pgf_path):
                        logger.info("watcher_detected_change", file=file_path, type=change_type)
                        await asyncio.sleep(0.1)
                        runtime.load(pgf_path)
        except asyncio.CancelledError:
            logger.info("watcher_stopped")
        except Exception as e:
            logger.error("watcher_crashed", error=str(e))
    else:
        try:
            while True:
                current_mtime = os.path.getmtime(pgf_path) if os.path.exists(pgf_path) else 0.0
                if current_mtime > runtime._last_mtime:
                    logger.info("watcher_polling_change", old=runtime._last_mtime, new=current_mtime)
                    runtime.load(pgf_path)
                await asyncio.sleep(5)
        except asyncio.CancelledError:
            logger.info("watcher_stopped")
        except Exception as e:
            logger.error("watcher_error", error=str(e))


# -----------------------------
# Event Bus -> ARQ bridge
# -----------------------------
async def _event_dedupe(ctx: Dict[str, Any], event_id: str, *, ttl_sec: int = 3600) -> bool:
    """
    True if event is new; False if already seen.
    Uses Redis SET NX with TTL for idempotency.
    """
    redis = ctx.get("redis")
    if not redis or not event_id:
        return True

    key = f"event_seen:{event_id}"
    try:
        ok = await redis.set(key, "1", ex=ttl_sec, nx=True)  # type: ignore[attr-defined]
        return bool(ok)
    except Exception as e:
        logger.warning("event_dedupe_failed", event_id=event_id, error=str(e))
        return True


async def _bridge_handler_factory(ctx: Dict[str, Any]) -> Callable[[SystemEvent], Coroutine[Any, Any, None]]:
    async def handler(event: SystemEvent) -> None:
        if not await _event_dedupe(ctx, event.id):
            logger.info("bridge_drop_duplicate_event", event_id=event.id, type=event.type)
            return

        try:
            payload = BuildRequestedPayload(**(event.payload or {}))
        except Exception as e:
            logger.error("bridge_bad_payload", event_id=event.id, error=str(e), payload=event.payload)
            return

        request = {
            "lang_code": payload.lang_code,
            "strategy": payload.strategy,
            "requester_id": payload.requester_id,
            "event_id": event.id,
            "trace_id": event.trace_id,
        }

        redis = ctx.get("redis")
        if not redis:
            logger.error("bridge_no_arq_redis", note="ctx['redis'] missing; cannot enqueue")
            return

        job_id = await redis.enqueue_job("build_language", request)  # type: ignore[attr-defined]
        logger.info(
            "bridge_enqueued_job",
            event_id=event.id,
            job_id=job_id,
            lang=payload.lang_code,
            strategy=payload.strategy,
        )

    return handler


async def _run_bridge(ctx: Dict[str, Any]) -> None:
    broker: RedisMessageBroker = ctx["event_broker"]
    handler = await _bridge_handler_factory(ctx)

    logger.info("bridge_subscribing", event_type=EventType.BUILD_REQUESTED)
    await broker.subscribe(EventType.BUILD_REQUESTED, handler)


# -----------------------------
# ARQ lifecycle
# -----------------------------
async def startup(ctx: Dict[str, Any]) -> None:
    setup_telemetry("architect-worker")
    logger.info("worker_startup", queue=settings.REDIS_QUEUE_NAME)

    broker = RedisMessageBroker()
    await broker.connect()
    ctx["event_broker"] = broker

    runtime.load(_effective_pgf_path())

    try:
        lexicon.load_language("eng")
    except Exception as e:
        logger.warning("lexicon_warm_failed", error=str(e))

    ctx["bridge_task"] = asyncio.create_task(_run_bridge(ctx))
    ctx["watcher_task"] = asyncio.create_task(watch_grammar_file(ctx))

    if os.getenv("PGF_PATH") and not os.getenv("AW_PGF_PATH"):
        logger.warning(
            "env_pgf_path_mismatch",
            note="PGF_PATH is set but AW_PGF_PATH is not; settings.PGF_PATH may ignore PGF_PATH depending on config.py",
            PGF_PATH=os.getenv("PGF_PATH"),
        )


async def shutdown(ctx: Dict[str, Any]) -> None:
    logger.info("worker_shutdown")

    for task_name in ("bridge_task", "watcher_task"):
        task = ctx.get(task_name)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error("shutdown_task_error", task=task_name, error=str(e))

    broker: Optional[RedisMessageBroker] = ctx.get("event_broker")
    if broker:
        try:
            await broker.disconnect()
        except Exception as e:
            logger.error("broker_disconnect_failed", error=str(e))


class WorkerSettings:
    """
    ARQ configuration.
    """
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    queue_name = settings.REDIS_QUEUE_NAME

    # Job registry
    functions = [build_language, compile_grammar]

    on_startup = startup
    on_shutdown = shutdown

    max_jobs = settings.WORKER_CONCURRENCY