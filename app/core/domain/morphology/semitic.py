# morphology\semitic.py
"""
morphology/semitic.py

A generic, data-driven morphology engine for Semitic languages
(e.g. Arabic, Hebrew, Amharic), built around a root-and-pattern model.

This engine is intentionally conservative and heavily configuration-driven:
most language-specific behaviour (broken plurals, patterns, case endings,
definiteness markers, etc.) lives in the per-language config rather than
in hard-coded rules.

Expected (but not strictly required) config shape
-------------------------------------------------

config = {
    "irregular": {
        "NOUN": {
            "rajul": {
                # keyed by feature bundles or simple labels
                # You can choose either style; see below.
                "number=pl": "rijal",
                "number=sg": "rajul",
            }
        },
        "VERB": {
            "kAtab": {
                "past,3,sg,m": "kataba"
            }
        }
    },

    # Optional: map surface lemmas to abstract roots
    "lemma_roots": {
        "kataba": "ktb",
        "maktab": "mktb"
    },

    "patterns": {
        "NOUN": [
            {
                "id": "fa3al",
                "when": {"number": "sg"},
                "template": "C1aC2aC3"
            },
            {
                "id": "fu3ul",
                "when": {"number": "pl"},
                "template": "C1uC2uC3"
            }
        ],
        "VERB": [
            {
                "id": "perfect_3sgm",
                "when": {
                    "tense": "past",
                    "person": "3",
                    "number": "sg",
                    "gender": "m",
                },
                "template": "C1aC2aC3a"
            }
        ]
    },

    "affixes": {
        "NOUN": {
            "prefixes": [
                {
                    "id": "definite_article",
                    "form": "al-",
                    "when": {"definiteness": "def"}
                }
            ],
            "suffixes": [
                {
                    "id": "nunation_nom",
                    "form": "un",
                    "when": {
                        "case": "nom",
                        "definiteness": "indef",
                    }
                }
            ]
        }
    },

    "orthography": {
        # Optional tweaks at the very end,
        # e.g. assimilation of /l/ to sun letters.
        # This is applied as a final post-processing step.
        "sun_letters": [
            "t", "th", "d", "dh", "r", "z", "s", "sh",
            "ṣ", "ḍ", "ṭ", "ẓ", "l", "n",
        ],
        "definite_article": "al-",
        "apply_sun_assimilation": True
    }
}
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Tuple

from .base import (
    FeatureDict,
    MorphologyEngine,
    MorphologyError,
    MorphRequest,
    MorphResult,
    register_engine,
)


def _features_to_key(features: FeatureDict) -> str:
    """
    Turn a feature bundle into a simple, deterministic key.

    This is used to query the `irregular` section of the config. It allows
    two styles of configuration:

    1. Fully explicit string keys, e.g. "number=pl,gender=f"
    2. Partial keys that match a subset of features, e.g. "number=pl"

    We generate all subset keys sorted by length and look for the most
    specific one that exists in the irregular dict.
    """
    if not features:
        return ""
    parts = [f"{k}={v}" for k, v in sorted(features.items())]
    return ",".join(parts)


def _match_conditions(when: Mapping[str, str], features: FeatureDict) -> bool:
    """
    Return True if all conditions in `when` are satisfied by the feature bundle.
    """
    for key, val in when.items():
        if features.get(key) != val:
            return False
    return True


def _select_best_pattern(
    patterns: List[Mapping[str, Any]],
    features: FeatureDict,
) -> Mapping[str, Any] | None:
    """
    Choose the best matching pattern from a list, based on 'when' constraints.

    Scoring:
        - Only patterns whose 'when' constraints are fully satisfied
          are considered.
        - Among those, the pattern with the largest number of
          constraints wins.
        - If there is a tie, the first in the list wins.
    """
    best: Mapping[str, Any] | None = None
    best_score = -1

    for pattern in patterns:
        cond: Mapping[str, str] = pattern.get("when", {}) or {}
        if not _match_conditions(cond, features):
            continue
        score = len(cond)
        if score > best_score:
            best_score = score
            best = pattern

    return best


def _extract_root(lemma: str, config: Mapping[str, Any]) -> str:
    """
    Return the root representation for a given lemma.

    By default, this looks up `config["lemma_roots"][lemma]` if present,
    otherwise it treats the lemma itself as a sequence of radicals.

    For a simple three-radical system, this can be just "ktb", which will
    then be split into ['k', 't', 'b'].
    """
    lemma_roots: Mapping[str, str] = config.get(
        "lemma_roots", {}
    )  # type: ignore[assignment]
    return lemma_roots.get(lemma, lemma)


def _fill_template(template: str, root: str) -> str:
    """
    Fill a root-and-pattern template.

    Expected placeholders in `template` are "C1", "C2", "C3", "C4".
    The `root` string is interpreted as a sequence of radicals; for a
    3-radical root this could be "ktb" → C1='k', C2='t', C3='b'.

    The function is deliberately simple and does not attempt to handle
    complex orthographic issues (gemination markers, long vowels, etc.).
    Those belong either in the config or in higher layers.
    """
    radicals: List[str] = list(root)
    if not radicals:
        return template

    # Allow underspecified roots; missing radicals are ignored.
    for i, radical in enumerate(radicals[:4]):
        placeholder = f"C{i + 1}"
        template = template.replace(placeholder, radical)

    return template


def _apply_affixes(
    stem: str,
    pos: str,
    features: FeatureDict,
    config: Mapping[str, Any],
    debug: Dict[str, Any],
) -> str:
    """
    Apply simple prefix and suffix rules based on `config["affixes"]`.

    Structure:

        "affixes": {
            "NOUN": {
                "prefixes": [
                    {
                        "id": "def_article",
                        "form": "al-",
                        "when": {"definiteness": "def"},
                    }
                ],
                "suffixes": [
                    {
                        "id": "nunation_nom",
                        "form": "un",
                        "when": {
                            "case": "nom",
                            "definiteness": "indef",
                        },
                    }
                ]
            }
        }

    Multiple prefixes/suffixes can fire; they are applied in the given
    order.
    """
    affixes_cfg: Mapping[str, Any] = config.get(
        "affixes", {}
    )  # type: ignore[assignment]
    pos_cfg: Mapping[str, Any] = affixes_cfg.get(pos, {})  # type: ignore[assignment]

    applied: List[str] = []
    surface = stem

    # Prefixes
    for rule in pos_cfg.get("prefixes", []) or []:
        cond = rule.get("when", {}) or {}
        if _match_conditions(cond, features):
            form = rule.get("form", "")
            if form:
                surface = f"{form}{surface}"
                applied.append(rule.get("id", form))

    # Suffixes
    for rule in pos_cfg.get("suffixes", []) or []:
        cond = rule.get("when", {}) or {}
        if _match_conditions(cond, features):
            form = rule.get("form", "")
            if form:
                surface = f"{surface}{form}"
                applied.append(rule.get("id", form))

    if applied:
        debug["affix_rules"] = applied

    return surface


def _apply_orthography(
    surface: str,
    config: Mapping[str, Any],
    debug: Dict[str, Any],
) -> str:
    """
    Optional final orthographic post-processing.

    For example, assimilation of the definite article 'al-' to sun
    letters in Arabic. This is left intentionally simple and controlled
    by config.
    """
    ortho: Mapping[str, Any] = config.get("orthography", {})  # type: ignore[assignment]
    if not ortho:
        return surface

    if not ortho.get("apply_sun_assimilation"):
        return surface

    article = ortho.get("definite_article", "al-")
    sun_letters: List[str] = ortho.get("sun_letters", [])

    if surface.startswith(article):
        # naive: check the next character (or digraph) and assimilate /l/
        remainder = surface[len(article) :]
        if not remainder:
            return surface

        # Check first one or two characters to approximate digraphs
        # like "sh".
        first_two = remainder[:2]
        first_one = remainder[0]

        target_letter: str | None = None
        if first_two in sun_letters:
            target_letter = first_two
        elif first_one in sun_letters:
            target_letter = first_one

        if target_letter:
            # Replace 'l' with the following consonant; for simplicity
            # we just double the consonant and drop 'l'.
            # "al+sh" -> "ashsh...", "al+s" -> "ass..."
            debug["sun_assimilation"] = {"letter": target_letter}
            surface = "a" + target_letter + remainder

    return surface


@register_engine("semitic")
class SemiticMorphologyEngine(MorphologyEngine):
    """
    Generic root-and-pattern morphology engine for Semitic languages.

    Behaviour is almost entirely driven by the supplied `config` dict;
    the engine itself only provides generic mechanisms:

        1. Check for irregular forms.
        2. Resolve lemma → root.
        3. Select an appropriate pattern based on feature constraints.
        4. Fill the pattern with radicals to obtain a stem.
        5. Apply affixes (prefixes/suffixes).
        6. Apply final orthographic tweaks.

    This is designed to be "good enough" for structured NLG in an
    Abstract-Wikipedia-style setting, not a full morphological analyser.
    """

    def inflect(self, request: MorphRequest) -> MorphResult:
        debug: Dict[str, Any] = {
            "request": {
                "lemma": request.lemma,
                "pos": request.pos,
                "features": dict(request.features),
                "language_code": request.language_code,
            }
        }

        # 1. Try irregular table first
        irregular = self._lookup_irregular(request, debug)
        if irregular is not None:
            surface = _apply_orthography(irregular, self.config, debug)
            debug["final_surface"] = surface
            return MorphResult(
                surface=surface,
                lemma=request.lemma,
                pos=request.pos,
                features=request.features,
                debug=debug,
            )

        # 2. Root extraction
        root = _extract_root(request.lemma, self.config)
        debug["root"] = root

        # 3. Pattern selection
        pattern = self._select_pattern(request, debug)
        if pattern is None:
            raise MorphologyError(
                "No suitable pattern found for "
                f"lemma='{request.lemma}', "
                f"pos='{request.pos}', "
                f"features={dict(request.features)}",
            )

        template: str = pattern.get("template", request.lemma)
        debug["pattern"] = {
            "id": pattern.get("id"),
            "template": template,
            "when": pattern.get("when", {}),
        }

        # 4. Fill pattern with radicals
        stem = _fill_template(template, root)
        debug["stem"] = stem

        # 5. Affixes
        surface = _apply_affixes(
            stem,
            request.pos,
            request.features,
            self.config,
            debug,
        )

        # 6. Orthography
        surface = _apply_orthography(surface, self.config, debug)
        debug["final_surface"] = surface

        return MorphResult(
            surface=surface,
            lemma=request.lemma,
            pos=request.pos,
            features=request.features,
            debug=debug,
        )

    # ------------------------------------------------------------------ #
    # Helper methods                                                     #
    # ------------------------------------------------------------------ #

    def _lookup_irregular(
        self,
        request: MorphRequest,
        debug: Dict[str, Any],
    ) -> str | None:
        """
        Look up an irregular form in `config["irregular"][pos][lemma]`.

        Supports two styles:

        1. Exact feature string keys:

            "irregular": {
                "NOUN": {
                    "rajul": {
                        "number=pl,gender=m": "rijal"
                    }
                }
            }

        2. Partially specified keys:

            "irregular": {
                "NOUN": {
                    "rajul": {
                        "number=pl": "rijal"
                    }
                }
            }

        In case of multiple matches, the most specific key (with most
        feature constraints) wins.
        """
        irregular_cfg: Mapping[str, Any] = self.config.get(
            "irregular", {}
        )  # type: ignore[assignment]
        pos_dict: Mapping[str, Any] = irregular_cfg.get(
            request.pos, {}
        )  # type: ignore[assignment]
        lemma_dict: Mapping[str, Any] = pos_dict.get(
            request.lemma, {}
        )  # type: ignore[assignment]

        if not lemma_dict:
            return None

        # Precompute feature key and all its subsets
        features = dict(request.features)
        if not features:
            form = lemma_dict.get("") or lemma_dict.get("default")
            if form:
                debug["irregular"] = {"key": "", "form": form}
            return form

        items = sorted(features.items())
        subsets: List[Tuple[Tuple[str, str], ...]] = []

        # Generate subsets with decreasing size
        for r in range(len(items), 0, -1):

            def _combinations(
                seq: List[Tuple[str, str]],
                r_size: int,
            ) -> List[Tuple[Tuple[str, str], ...]]:
                result: List[Tuple[Tuple[str, str], ...]] = []

                def _recurse(
                    start: int,
                    path: Tuple[Tuple[str, str], ...],
                ) -> None:
                    if len(path) == r_size:
                        result.append(path)
                        return
                    for i in range(start, len(seq)):
                        _recurse(i + 1, path + (seq[i],))

                _recurse(0, ())
                return result

            subsets.extend(_combinations(items, r))
            if subsets:
                break  # we only need the largest size

        for subset in subsets:
            key = ",".join(f"{k}={v}" for k, v in subset)
            if key in lemma_dict:
                form = lemma_dict[key]
                debug["irregular"] = {"key": key, "form": form}
                return form

        # Try a generic "default" entry
        default_form = lemma_dict.get("default")
        if default_form:
            debug["irregular"] = {"key": "default", "form": default_form}
        return default_form

    def _select_pattern(
        self,
        request: MorphRequest,
        debug: Dict[str, Any],
    ) -> Mapping[str, Any] | None:
        """
        Select a root-and-pattern template from `config["patterns"][pos]`.
        """
        patterns_cfg: Mapping[str, Any] = self.config.get(
            "patterns", {}
        )  # type: ignore[assignment]
        pos_patterns: List[Mapping[str, Any]] = patterns_cfg.get(
            request.pos, []
        )  # type: ignore[assignment]

        if not pos_patterns:
            debug["pattern"] = {
                "error": (f"no patterns configured for pos '{request.pos}'")
            }
            return None

        pattern = _select_best_pattern(pos_patterns, request.features)
        if pattern is None:
            debug["pattern"] = {
                "error": "no pattern matched feature bundle",
                "features": dict(request.features),
            }
        return pattern
