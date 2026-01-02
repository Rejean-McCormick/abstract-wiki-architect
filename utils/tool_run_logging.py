# utils/tool_run_logging.py
import logging
import sys
import time
import uuid
import os
from contextlib import contextmanager

def init_stdout_logging(name: str):
    """
    Initializes logging to stdout with a consistent format.
    Force reconfigures the root logger to ensure messages appear in the GUI console.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
        force=True
    )
    return logging.getLogger(name)

def generate_run_id() -> str:
    """Generates a short, unique run ID for tracking."""
    return str(uuid.uuid4())[:8]

class ToolRunContext:
    """
    Context manager for tracking tool execution stages and timing.
    """
    def __init__(self, tool_name: str):
        self.tool_name = tool_name
        self.run_id = generate_run_id()
        self.start_time = time.time()
        self.logger = init_stdout_logging(tool_name)
        self._print_header()

    def _print_header(self):
        cwd = os.getcwd()
        self.logger.info(f"=== TOOL RUN START: {self.tool_name} (ID: {self.run_id}) ===")
        self.logger.info(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info(f"CWD:  {cwd}")

    def log_stage(self, stage_name: str):
        self.logger.info(f"--- STAGE: {stage_name} ---")

    def finish(self, summary: dict = None):
        duration = time.time() - self.start_time
        self.logger.info(f"=== TOOL RUN FINISHED ({duration:.2f}s) ===")
        if summary:
            self.logger.info("Summary:")
            for k, v in summary.items():
                self.logger.info(f"  {k}: {v}")

@contextmanager
def tool_logging(name: str):
    ctx = ToolRunContext(name)
    try:
        yield ctx
    except Exception as e:
        ctx.logger.error(f"!!! TOOL FAILED !!!", exc_info=True)
        ctx.logger.error(f"Failure Stage: [Check last log entry]")
        # We re-raise so the GUI or wrapper sees the non-zero exit code
        raise
    finally:
        # Optional: any cleanup
        pass