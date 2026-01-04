# tools/everything_matrix/scoring.py
from __future__ import annotations

from typing import Any, Iterable, Mapping


def clamp10(x: Any) -> float:
    try:
        v = float(x)
    except Exception:
        return 0.0
    if v < 0:
        return 0.0
    if v > 10:
        return 10.0
    return v


def maybe_rescale_01_to_10(x: Any) -> float:
    """
    Back-compat shim:
      - If value is in [0,1], treat as ratio and scale to [0,10]
      - If already > 1, assume [0,10]
    """
    v = clamp10(x)
    if v > 1.0:
        return v
    return clamp10(round(v * 10.0, 2))


def mean(values: Iterable[float]) -> float:
    vals = [float(v) for v in values]
    return (sum(vals) / len(vals)) if vals else 0.0


def normalize_weights(weights: Mapping[str, Any], keys: Iterable[str]) -> dict[str, float]:
    out: dict[str, float] = {}
    total = 0.0
    keys_list = list(keys)

    for k in keys_list:
        try:
            w = float(weights.get(k, 0.0))
        except Exception:
            w = 0.0
        if w < 0:
            w = 0.0
        out[k] = w
        total += w

    if total <= 0:
        n = len(keys_list) if keys_list else 1
        return {k: 1.0 / n for k in keys_list}

    return {k: out[k] / total for k in out}


def zone_a_from_modules(modules: Mapping[str, Any]) -> dict[str, float]:
    keys = set(str(k) for k in (modules.keys() if isinstance(modules, Mapping) else []))
    return {
        "CAT": 10.0 if "Cat" in keys else 0.0,
        "NOUN": 10.0 if ("Noun" in keys or "Nouns" in keys) else 0.0,
        "PARA": 10.0 if "Paradigms" in keys else 0.0,
        "GRAM": 10.0 if "Grammar" in keys else 0.0,
        "SYN": 10.0 if "Syntax" in keys else 0.0,
    }


def apply_zone_a_strategy_map(zone_a: Mapping[str, float], build_strategy: str) -> dict[str, float]:
    """
    In SAFE_MODE + CAT present, give partial credit for missing modules.
    """
    out = {k: clamp10(v) for k, v in zone_a.items()}
    if build_strategy != "SAFE_MODE":
        return out
    if out.get("CAT", 0.0) < 10.0:
        return out
    for k in ("NOUN", "PARA", "GRAM", "SYN"):
        if out.get(k, 0.0) <= 0.0:
            out[k] = 5.0
    return out


def zone_averages(zone_a: Mapping[str, float], zone_b: Mapping[str, float], zone_c: Mapping[str, float], zone_d: Mapping[str, float]) -> dict[str, float]:
    return {
        "A_RGL": round(mean([clamp10(v) for v in zone_a.values()]), 2),
        "B_LEX": round(mean([clamp10(v) for v in zone_b.values()]), 2),
        "C_APP": round(mean([clamp10(v) for v in zone_c.values()]), 2),
        "D_QA": round(mean([clamp10(v) for v in zone_d.values()]), 2),
    }


def maturity(zone_avgs: Mapping[str, float], weights: Mapping[str, float]) -> float:
    keys = ("A_RGL", "B_LEX", "C_APP", "D_QA")
    w_norm = normalize_weights(weights, keys)
    score = 0.0
    for k in keys:
        score += float(w_norm.get(k, 0.0)) * float(zone_avgs.get(k, 0.0))
    return round(clamp10(score), 1)


def choose_build_strategy(
    *,
    iso2: str,
    maturity_score: float,
    zone_a: Mapping[str, float],
    zone_b: Mapping[str, float],
    zone_d: Mapping[str, float],
    factory_registry: Mapping[str, Any],
    cfg_matrix: Mapping[str, Any],
) -> str:
    high_cfg = cfg_matrix.get("high_road", {}) if isinstance(cfg_matrix.get("high_road"), dict) else {}
    skip_cfg = cfg_matrix.get("skip", {}) if isinstance(cfg_matrix.get("skip"), dict) else {}

    # [FIX] Lowered min_maturity from 8.0 to 4.0.
    # Logic: Zone A (RGL) weight is 0.40. If RGL is perfect (10.0), score is 4.0.
    # This allows languages with RGL but no App/QA to still build as HIGH_ROAD.
    min_maturity = float(high_cfg.get("min_maturity", 4.0))
    
    min_cat = float(high_cfg.get("min_cat", 10.0))
    min_seed = float(high_cfg.get("min_seed", 2.0))
    min_bin = float(high_cfg.get("min_bin", 0.0))
    min_a_avg = float(skip_cfg.get("min_a_avg", 2.0))

    is_factory = iso2 in factory_registry
    cat = float(zone_a.get("CAT", 0.0))
    seed = float(zone_b.get("SEED", 0.0))
    bin_score = float(zone_d.get("BIN", 0.0))
    a_avg = mean([float(v) for v in zone_a.values()]) if zone_a else 0.0

    if (a_avg < min_a_avg) and (not is_factory):
        return "SKIP"

    if maturity_score >= min_maturity and cat >= min_cat and seed >= min_seed:
        if min_bin > 0.0 and bin_score < min_bin:
            return "SAFE_MODE"
        return "HIGH_ROAD"

    return "SAFE_MODE"