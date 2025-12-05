"""
nlg/cli_frontend.py

Command-line interface for the high-level NLG frontend API.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# --- BOOTSTRAP: Add project root to sys.path ---
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_current_dir)
if _project_root not in sys.path:
    sys.path.append(_project_root)
# -----------------------------------------------

from nlg.api import generate, GenerationOptions
from semantics.normalization import normalize_bio_semantics
from semantics.types import BioFrame, Entity


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nlg-cli",
        description="CLI frontend for the NLG API (frame → text).",
    )

    subparsers = parser.add_subparsers(
        title="commands",
        dest="command",
        required=True,
    )

    # `generate` command
    gen = subparsers.add_parser(
        "generate",
        help="Generate text for a given language and frame.",
    )

    gen.add_argument(
        "--lang",
        required=True,
        help="Target language code (e.g. 'en', 'fr', 'sw').",
    )

    gen.add_argument(
        "--frame-type",
        help=(
            "Frame type label (e.g. 'bio', 'event'). "
            "If omitted, the JSON must contain a 'frame_type' field."
        ),
    )

    gen.add_argument(
        "--input",
        "-i",
        metavar="PATH",
        help=(
            "Path to a JSON file containing the frame. "
            "If omitted or '-', read from stdin."
        ),
    )

    gen.add_argument(
        "--max-sentences",
        type=int,
        default=None,
        help="Optional upper bound on the number of sentences to generate.",
    )

    gen.add_argument(
        "--register",
        choices=["neutral", "formal", "informal"],
        default=None,
        help="Optional register/style hint.",
    )

    gen.add_argument(
        "--discourse-mode",
        default=None,
        help="Optional discourse mode hint (e.g. 'intro', 'summary').",
    )

    gen.add_argument(
        "--debug",
        action="store_true",
        help="Include debug information from the generator.",
    )

    return parser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_json(path: Optional[str]) -> Dict[str, Any]:
    """
    Load a JSON object from a file or stdin.
    """
    if not path or path == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(path).read_text(encoding="utf-8")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Error: invalid JSON input ({exc}).") from exc

    if not isinstance(data, dict):
        raise SystemExit("Error: expected a JSON object at top level.")

    return data


def _ensure_frame_type(payload: Dict[str, Any], frame_type_arg: Optional[str]) -> None:
    """
    Ensure that the payload has a 'frame_type' key.
    """
    if frame_type_arg:
        payload.setdefault("frame_type", frame_type_arg)

    if "frame_type" not in payload or not payload["frame_type"]:
        raise SystemExit(
            "Error: frame type not specified. "
            "Use --frame-type or include 'frame_type' in the JSON."
        )


def _build_generation_options(args: argparse.Namespace) -> GenerationOptions:
    """
    Construct a GenerationOptions instance from CLI arguments.
    """
    return GenerationOptions(
        register=args.register,
        max_sentences=args.max_sentences,
        discourse_mode=args.discourse_mode,
        seed=None,
    )


def _convert_to_bio_frame(normalized_semantics) -> BioFrame:
    """
    Convert the normalized BioSemantics object into a BioFrame
    that the engine expects.
    """
    # Create the Entity object
    entity = Entity(
        name=normalized_semantics.name,
        gender=normalized_semantics.gender,
        human=True,  # Bios are usually human
    )

    # Create lists for lemmas (BioSemantics has strings, BioFrame expects lists)
    prof_lemmas = (
        [normalized_semantics.profession_lemma]
        if normalized_semantics.profession_lemma
        else []
    )
    nat_lemmas = (
        [normalized_semantics.nationality_lemma]
        if normalized_semantics.nationality_lemma
        else []
    )

    return BioFrame(
        main_entity=entity,
        primary_profession_lemmas=prof_lemmas,
        nationality_lemmas=nat_lemmas,
        extra=normalized_semantics.extra,
    )


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------


def _cmd_generate(args: argparse.Namespace) -> int:
    """
    Handle `nlg-cli generate` command.
    """
    payload = _load_json(args.input)
    _ensure_frame_type(payload, args.frame_type)

    # Normalize input based on frame type
    frame_type = payload.get("frame_type")

    if frame_type == "bio":
        # 1. Normalize raw JSON to BioSemantics
        semantics = normalize_bio_semantics(payload)
        # 2. Convert BioSemantics to BioFrame (required by the API/Engine)
        frame = _convert_to_bio_frame(semantics)
    else:
        # Fallback for other types
        frame = payload

    options = _build_generation_options(args)

    result = generate(
        lang=args.lang,
        frame=frame,
        options=options,
        debug=args.debug,
    )

    # Main output: realized text
    if result.text:
        print(result.text)
    else:
        # If empty, print a warning to stderr so we know something happened
        print("[No output generated]", file=sys.stderr)

    # Optional debug output to stderr
    if args.debug and getattr(result, "debug_info", None) is not None:
        debug_serialized = json.dumps(
            result.debug_info,
            indent=2,
            ensure_ascii=False,
        )
        print("\n[DEBUG]", file=sys.stderr)
        print(debug_serialized, file=sys.stderr)

    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: Optional[list[str]] = None) -> None:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    if args.command == "generate":
        exit_code = _cmd_generate(args)
    else:
        parser.error(f"Unknown command: {args.command}")
        return

    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
