# tests/integration/test_worker_flow.py
import json
import os
from unittest.mock import AsyncMock, mock_open, patch

import pytest

from app.core.domain.events import EventType, SystemEvent
from app.workers.worker import compile_grammar


@pytest.mark.asyncio
class TestWorkerFlow:
    """
    Integration-style tests for the ARQ job function in app/workers/worker.py.
    Note: There is no BuildTaskHandler class in the current codebase.
    """

    async def test_build_requested_event_triggers_compile_job(self):
        # Arrange: simulate the domain event payload (producer side)
        event = SystemEvent(
            type=EventType.BUILD_REQUESTED,
            payload={"lang_code": "deu", "strategy": "full"},
        )
        lang_code = event.payload["lang_code"]

        base_dir = "/repo"
        pgf_path = f"{base_dir}/gf/AbstractWiki.pgf"
        src_file = f"{base_dir}/gf/WikiGer.gf"  # expected via iso_to_wiki mapping for 'deu' -> 'Ger'

        iso_map = {"deu": {"wiki": "Ger"}}

        def fake_os_exists(path: str) -> bool:
            p = str(path)
            return p in {src_file, pgf_path}

        def fake_path_exists(self) -> bool:
            # Only claim the iso_to_wiki file exists; all other Path.exists() checks -> False
            return str(self).replace("\\", "/").endswith("/data/config/iso_to_wiki.json")

        mock_proc = type(
            "Proc",
            (),
            {"returncode": 0, "stdout": "Wrote AbstractWiki.pgf", "stderr": ""},
        )()

        # Act
        with patch.dict(os.environ, {"AW_PGF_PATH": pgf_path}, clear=False), \
             patch("app.workers.worker.settings.FILESYSTEM_REPO_PATH", base_dir), \
             patch("app.workers.worker.os.path.exists", side_effect=fake_os_exists), \
             patch("app.workers.worker.Path.exists", fake_path_exists), \
             patch("builtins.open", mock_open(read_data=json.dumps(iso_map))), \
             patch("app.workers.worker.asyncio.to_thread", new_callable=AsyncMock, return_value=mock_proc) as mock_to_thread, \
             patch("app.workers.worker.runtime.reload", new_callable=AsyncMock) as mock_reload:

            result = await compile_grammar({}, lang_code, trace_context=None)

        # Assert
        assert result == "Compiled deu successfully."

        mock_reload.assert_called_once()

        mock_to_thread.assert_awaited_once()
        args, kwargs = mock_to_thread.call_args
        assert args[0].__name__ == "run"  # subprocess.run
        cmd = args[1]
        assert cmd[0] == "gf"
        assert "-batch" in cmd
        assert "-make" in cmd
        assert src_file in cmd
        assert kwargs["cwd"] == f"{base_dir}/gf"
        assert kwargs["capture_output"] is True
        assert kwargs["text"] is True

    async def test_source_file_missing_returns_message(self):
        base_dir = "/repo"
        pgf_path = f"{base_dir}/gf/AbstractWiki.pgf"
        src_file = f"{base_dir}/gf/WikiXyz.gf"  # 'xyz' -> 'Xyz' fallback

        def fake_os_exists(path: str) -> bool:
            # Source file missing -> early return (no subprocess call)
            return str(path) != src_file

        with patch.dict(os.environ, {"AW_PGF_PATH": pgf_path}, clear=False), \
             patch("app.workers.worker.settings.FILESYSTEM_REPO_PATH", base_dir), \
             patch("app.workers.worker.os.path.exists", side_effect=fake_os_exists), \
             patch("app.workers.worker.Path.exists", lambda _self: False), \
             patch("app.workers.worker.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread, \
             patch("app.workers.worker.runtime.reload", new_callable=AsyncMock) as mock_reload:

            result = await compile_grammar({}, "xyz", trace_context=None)

        assert result == f"Source file missing: {src_file}"
        mock_to_thread.assert_not_awaited()
        mock_reload.assert_not_called()

    async def test_compile_failure_raises_runtimeerror(self):
        base_dir = "/repo"
        pgf_path = f"{base_dir}/gf/AbstractWiki.pgf"
        src_file = f"{base_dir}/gf/WikiEng.gf"  # 'eng' -> 'Eng' fallback (no iso map)

        def fake_os_exists(path: str) -> bool:
            p = str(path)
            return p in {src_file, pgf_path}

        mock_proc = type(
            "Proc",
            (),
            {"returncode": 1, "stdout": "", "stderr": "Syntax error"},
        )()

        with patch.dict(os.environ, {"AW_PGF_PATH": pgf_path}, clear=False), \
             patch("app.workers.worker.settings.FILESYSTEM_REPO_PATH", base_dir), \
             patch("app.workers.worker.os.path.exists", side_effect=fake_os_exists), \
             patch("app.workers.worker.Path.exists", lambda _self: False), \
             patch("app.workers.worker.asyncio.to_thread", new_callable=AsyncMock, return_value=mock_proc), \
             patch("app.workers.worker.runtime.reload", new_callable=AsyncMock) as mock_reload:

            with pytest.raises(RuntimeError) as excinfo:
                await compile_grammar({}, "eng", trace_context=None)

        assert "GF Compilation Failed" in str(excinfo.value)
        mock_reload.assert_not_called()
