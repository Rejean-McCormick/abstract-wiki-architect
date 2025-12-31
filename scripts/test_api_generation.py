# scripts/test_api_generation.py
import os
import uuid
import json
import requests
from typing import Any, Dict, Optional, Tuple

# Base URL per docs: http://localhost:8000/api/v1
# You can override:
#   Windows (PowerShell):  $env:AWA_BASE_URL="http://localhost:8000/api/v1"
#   macOS/Linux:          export AWA_BASE_URL="http://localhost:8000/api/v1"
BASE_URL = os.getenv("AWA_BASE_URL", "http://localhost:8000/api/v1").rstrip("/")

# Optional (production): set AWA_API_KEY to send X-API-Key
API_KEY = os.getenv("AWA_API_KEY")

# Optional: set to reuse discourse context for pronouns across calls
# If not set, a fresh session is generated each run.
SESSION_ID = os.getenv("AWA_SESSION_ID")  # e.g., "2a0a3f22-...."

DEFAULT_TIMEOUT_SEC = float(os.getenv("AWA_TIMEOUT_SEC", "30"))


def _headers(session_id: Optional[str]) -> Dict[str, str]:
    h = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if API_KEY:
        h["X-API-Key"] = API_KEY
    if session_id:
        h["X-Session-ID"] = session_id
    return h


def _try_request(
    url: str,
    payload: Dict[str, Any],
    params: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None,
) -> Tuple[int, str, Optional[Dict[str, Any]]]:
    """
    Returns: (status_code, raw_text, parsed_json_or_none)
    """
    resp = requests.post(
        url,
        json=payload,
        params=params or {},
        headers=_headers(session_id),
        timeout=DEFAULT_TIMEOUT_SEC,
    )

    raw = resp.text
    try:
        data = resp.json()
    except ValueError:
        data = None

    return resp.status_code, raw, data


def generate_bio(lang_code: str, name: str, profession: str, nationality: str, gender: Optional[str] = None,
                 style: Optional[str] = None, session_id: Optional[str] = None) -> None:
    """
    Canonical (docs):
      POST {BASE_URL}/generate/{lang_code}
      Body: {frame_type, name, profession, nationality, gender}
      Optional query: ?style=simple|formal
      Optional header: X-Session-ID (discourse context)
    """
    print(f"\n--- Testing {lang_code.upper()} ---")

    # Strict Path (BioFrame) per docs (single flat JSON object)
    frame_payload: Dict[str, Any] = {
        "frame_type": "bio",
        "name": name,
        "profession": profession,
        "nationality": nationality,
    }
    if gender is not None:
        frame_payload["gender"] = gender  # "m" | "f" | None

    # Try canonical endpoint first
    url_v2 = f"{BASE_URL}/generate/{lang_code}"
    params = {}
    if style:
        params["style"] = style

    try:
        status, raw, data = _try_request(url_v2, frame_payload, params=params, session_id=session_id)

        # Fallbacks to tolerate older servers / split-brain endpoints:
        # 1) /generate?lang=xx  with body = frame
        # 2) /generate          with body = {lang, frame, options}
        if status in (404, 405, 422):
            url_legacy_qp = f"{BASE_URL}/generate"
            status2, raw2, data2 = _try_request(
                url_legacy_qp,
                frame_payload,
                params={"lang": lang_code, **params},
                session_id=session_id,
            )
            if status2 not in (404, 405, 422):
                status, raw, data = status2, raw2, data2
            else:
                wrapper_payload = {
                    "lang": lang_code,
                    "frame": frame_payload,
                    "options": {"style": style or "simple"},
                }
                status3, raw3, data3 = _try_request(
                    url_legacy_qp,
                    wrapper_payload,
                    params={},
                    session_id=session_id,
                )
                status, raw, data = status3, raw3, data3

        if status == 200:
            # Support both JSON and text responses
            if isinstance(data, dict):
                text = data.get("text") or data.get("result") or ""
                print(f"✅ SUCCESS: {text if text else '(empty)'}")
                debug = data.get("debug_info") or data.get("meta") or {}
                if isinstance(debug, dict) and debug:
                    engine = debug.get("engine") or debug.get("source") or "Unknown"
                    print(f"   (Debug/Engine: {engine})")
            else:
                # Plain text response
                print(f"✅ SUCCESS: {raw.strip() if raw.strip() else '(empty)'}")
        else:
            # Print the most useful error detail we can
            if isinstance(data, dict) and "detail" in data:
                print(f"❌ FAILED ({status}): {data['detail']}")
            else:
                print(f"❌ FAILED ({status}): {raw}")

    except requests.exceptions.ConnectionError:
        print("❌ FAILED: Could not connect to backend. Is uvicorn running?")
    except requests.exceptions.Timeout:
        print(f"❌ FAILED: Request timed out after {DEFAULT_TIMEOUT_SEC:.0f}s")
    except Exception as e:
        print(f"❌ FAILED: Unexpected error: {e}")


if __name__ == "__main__":
    # Use one session for the whole run unless overridden by env var.
    run_session_id = SESSION_ID or str(uuid.uuid4())

    # 1) French
    # NOTE: docs specify ISO 639-1 (2-letter) codes for {lang_code}.
    generate_bio(
        lang_code="fr",
        name="Marie Curie",
        profession="physicist",
        nationality="polish",
        gender="f",
        style="simple",
        session_id=run_session_id,
    )

    # 2) Korean (often stub / fallback depending on your build)
    generate_bio(
        lang_code="ko",
        name="Marie Curie",
        profession="physicist",
        nationality="polish",
        gender="f",
        style="simple",
        session_id=run_session_id,
    )
