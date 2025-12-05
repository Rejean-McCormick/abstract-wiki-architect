#!/usr/bin/env python3
"""
Update frame_type string literals in schemas/frames/*.schema.json and
qa/test_frames_*.py.

- Only the files listed in TARGET_FILES are touched.
- Only quoted string literals are rewritten (both "..." and '...').
- No backup / temp artifacts are left behind.
- By default it is a dry run; use --apply to actually modify files.

Usage:
    python tools/update_frame_type_strings.py           # dry run
    python tools/update_frame_type_strings.py --apply   # rewrite files in place
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict


# --------------------------------------------------------------------------------------
# 1. String mapping: OLD → NEW (canonical = semantics.all_frames.FRAME_FAMILIES)
# --------------------------------------------------------------------------------------

FRAME_TYPE_RENAMES: Dict[str, str] = {
    # Entity families (legacy → canonical)
    "sports-team": "entity.sports_team",
    "competition-league": "entity.competition",
    "product-brand": "entity.product_or_brand",
    "chemical-material": "entity.chemical",
    "astronomical-object": "entity.astronomical_object",
    "software-protocol-standard": "entity.software_or_standard",
    "project-program": "entity.project_or_program",
    "fictional-entity": "entity.fictional_entity",
    "religion-ideology": "entity.belief_system",
    "belief-system": "entity.belief_system",
    "discipline-theory": "entity.academic_discipline",
    "academic-discipline": "entity.academic_discipline",
    "law-treaty-policy": "entity.law_or_treaty",
    # Entity dotted legacy → canonical dotted
    "entity.product_brand": "entity.product_or_brand",
    "entity.competition_league": "entity.competition",
    "entity.religion_ideology": "entity.belief_system",
    "entity.fictional": "entity.fictional_entity",
    # Event families (legacy → canonical)
    "generic-event": "event.generic",
    "historical-event": "event.historical",
    "conflict-war-event": "event.conflict",
    "election-referendum": "event.election",
    "disaster-accident-event": "event.disaster",
    "scientific-technical-milestone-event": "event.scientific_milestone",
    "cultural-event": "event.cultural",
    "sports-event": "event.sports",
    "legal-case-event": "event.legal_case",
    "economic-financial-event": "event.economic",
    "exploration-expedition-mission": "event.exploration",
    "life-event": "event.life",
    # Event dotted legacy → canonical dotted
    "event.economic_financial": "event.economic",
    "event.exploration_mission": "event.exploration",
    # Relational families (legacy → canonical)
    "definition-classification": "relation.definition",
    "attribute-property": "relation.attribute",
    "quantitative-measure": "relation.quantitative",
    "comparative-ranking": "relation.comparative",
    "membership-affiliation": "relation.membership",
    "role-position-office": "relation.role",
    "part-whole-composition": "relation.part_whole",
    "ownership-control": "relation.ownership",
    "spatial-relation": "relation.spatial",
    "temporal-relation": "relation.temporal",
    "causal-influence": "relation.causal",
    "change-of-state": "relation.change_of_state",
    "communication-statement": "relation.communication",
    "opinion-evaluation": "relation.opinion",
    "relation-bundle": "relation.bundle",
    # Narrative / aggregate families (legacy → canonical)
    "timeline-chronology": "aggregate.timeline",
    "career-season-campaign-summary": "aggregate.career_summary",
    "development-evolution": "aggregate.development",
    "reception-impact": "aggregate.reception",
    "structure-organization": "aggregate.structure",
    "comparison-set-contrast": "aggregate.comparison_set",
    "list-enumeration": "aggregate.list",
    # Meta families (legacy → canonical)
    "article-document": "meta.article",
    "section-summary": "meta.section_summary",
    "source-citation": "meta.source",
}


# --------------------------------------------------------------------------------------
# 2. Files that this script is allowed to touch
# --------------------------------------------------------------------------------------

TARGET_FILES = [
    # Index
    "schemas/frames/frames_index.json",
    # Entity schemas
    "schemas/frames/entity_person.schema.json",
    "schemas/frames/entity_organization.schema.json",
    "schemas/frames/entity_geopolitical_entity.schema.json",
    "schemas/frames/entity_place.schema.json",
    "schemas/frames/entity_facility.schema.json",
    "schemas/frames/entity_astronomical_object.schema.json",
    "schemas/frames/entity_species.schema.json",
    "schemas/frames/entity_chemical_material.schema.json",
    "schemas/frames/entity_artifact.schema.json",
    "schemas/frames/entity_vehicle.schema.json",
    "schemas/frames/entity_creative_work.schema.json",
    "schemas/frames/entity_software_protocol_standard.schema.json",
    "schemas/frames/entity_product_brand.schema.json",
    "schemas/frames/entity_sports_team.schema.json",
    "schemas/frames/entity_competition_league.schema.json",
    "schemas/frames/entity_language.schema.json",
    "schemas/frames/entity_religion_ideology.schema.json",
    "schemas/frames/entity_discipline_theory.schema.json",
    "schemas/frames/entity_law_treaty_policy.schema.json",
    "schemas/frames/entity_project_program.schema.json",
    "schemas/frames/entity_fictional_entity.schema.json",
    # Event schemas
    "schemas/frames/event_generic_event.schema.json",
    "schemas/frames/event_historical_event.schema.json",
    "schemas/frames/event_conflict_war_event.schema.json",
    "schemas/frames/event_election_referendum_event.schema.json",
    "schemas/frames/event_disaster_accident_event.schema.json",
    "schemas/frames/event_scientific_technical_milestone_event.schema.json",
    "schemas/frames/event_cultural_event.schema.json",
    "schemas/frames/event_sports_event.schema.json",
    "schemas/frames/event_legal_case_event.schema.json",
    "schemas/frames/event_economic_financial_event.schema.json",
    "schemas/frames/event_exploration_expedition_mission_event.schema.json",
    "schemas/frames/event_life_event.schema.json",
    # Relational schemas
    "schemas/frames/relational_definition_classification.schema.json",
    "schemas/frames/relational_attribute_property.schema.json",
    "schemas/frames/relational_quantitative_measure.schema.json",
    "schemas/frames/relational_comparative_ranking.schema.json",
    "schemas/frames/relational_membership_affiliation.schema.json",
    "schemas/frames/relational_role_position_office.schema.json",
    "schemas/frames/relational_part_whole_composition.schema.json",
    "schemas/frames/relational_ownership_control.schema.json",
    "schemas/frames/relational_spatial_relation.schema.json",
    "schemas/frames/relational_temporal_relation.schema.json",
    "schemas/frames/relational_causal_influence.schema.json",
    "schemas/frames/relational_change_of_state.schema.json",
    "schemas/frames/relational_communication_statement.schema.json",
    "schemas/frames/relational_opinion_evaluation.schema.json",
    "schemas/frames/relational_relation_bundle.schema.json",
    # Narrative schemas
    "schemas/frames/narrative_timeline_chronology.schema.json",
    "schemas/frames/narrative_career_season_campaign_summary.schema.json",
    "schemas/frames/narrative_development_evolution.schema.json",
    "schemas/frames/narrative_reception_impact.schema.json",
    "schemas/frames/narrative_structure_organization.schema.json",
    "schemas/frames/narrative_comparison_set_contrast.schema.json",
    "schemas/frames/narrative_list_enumeration.schema.json",
    # Meta schemas
    "schemas/frames/meta_article_document.schema.json",
    "schemas/frames/meta_section_summary.schema.json",
    "schemas/frames/meta_source_citation.schema.json",
    # QA tests
    "qa/test_frames_entity.py",
    "qa/test_frames_event.py",
    "qa/test_frames_relational.py",
    "qa/test_frames_narrative.py",
    "qa/test_frames_meta.py",
]


# --------------------------------------------------------------------------------------
# 3. Core logic
# --------------------------------------------------------------------------------------


def apply_renames_to_text(text: str) -> str:
    """
    Replace quoted occurrences of old frame_type strings with new ones.

    We replace both "old" and 'old' to cover JSON and Python tests, but we
    do NOT touch unquoted occurrences.
    """
    new_text = text
    for old, new in FRAME_TYPE_RENAMES.items():
        if old == new:
            continue
        # Double-quoted
        new_text = new_text.replace(f'"{old}"', f'"{new}"')
        # Single-quoted
        new_text = new_text.replace(f"'{old}'", f"'{new}'")
    return new_text


def process_file(path: Path, apply: bool) -> bool:
    """
    Process a single file.

    Returns True if the file would be / was modified, False otherwise.
    """
    try:
        original = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"[SKIP] Missing file: {path}")
        return False

    updated = apply_renames_to_text(original)

    if updated == original:
        print(f"[OK]   No changes: {path}")
        return False

    if apply:
        path.write_text(updated, encoding="utf-8")
        print(f"[DONE] Updated: {path}")
    else:
        print(f"[DRY]  Would update: {path}")

    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rewrite frame_type string literals in schema + QA files."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually rewrite files instead of doing a dry run.",
    )
    parser.add_argument(
        "--root",
        type=str,
        default=".",
        help="Repo root (default: current directory).",
    )

    args = parser.parse_args()
    root = Path(args.root).resolve()

    any_changes = False
    for rel in TARGET_FILES:
        path = root / rel
        changed = process_file(path, apply=args.apply)
        any_changes = any_changes or changed

    if not any_changes:
        print("No files needed changes with the current mapping.")


if __name__ == "__main__":
    main()
