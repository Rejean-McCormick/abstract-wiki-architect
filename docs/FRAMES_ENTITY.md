
# Entity Frames

This document defines the **entity-level semantic frames** used (and planned) in Abstract Wiki Architect for encyclopedic subjects: people, organizations, places, works, products, etc.

The goal is to:

- Provide a **uniform inventory** of entity frames.
- Specify **field conventions** so bridges (e.g. AW/Z → internal semantics) can construct them consistently.
- Prepare the ground for **non-biographical entity sentences** in the same architecture that currently powers `BioFrame`-based biographies.

> Status
>
> - **Implemented in code:** `Entity`, `Location`, `TimeSpan`, `Event`, `BioFrame`.
> - **This document:** defines a broader entity-frame inventory and conventions. Most frames are **design-level** and need corresponding dataclasses / normalizers to be added incrementally.

---

## 1. Scope

**Entity frames** are semantic objects that model “things we can write an article about”:

- People and groups
- Places and facilities
- Languages, religions, ideologies
- Creative works, products, brands
- Laws, projects, fictional universes, etc.

They are:

- **Language-agnostic**: no surface forms, no grammar-specific choices.
- **Stable**: the same frame can be rendered into many languages.
- **Combinable**: they can be used alongside event frames and relational frames.

This document only covers **entity-centric** families. Event, relational, aggregate, and meta frames live in separate files:

- `docs/FRAMES_EVENT.md`
- `docs/FRAMES_RELATIONAL.md`
- `docs/FRAMES_NARRATIVE.md`
- `docs/FRAMES_META.md` (article / section level)

---

## 2. Shared building blocks and conventions

### 2.1 Core semantic units

All entity frames are built from the core semantic dataclasses:

- `Entity` – generic discourse entity (person, organization, place, abstract thing).
- `Location` – lightweight location entity (city, country, region, etc.).
- `TimeSpan` – coarse time interval (years, optional month/day).
- `Event` – semantic event or state (birth, founding, discovery, award…).
- `BioFrame` – higher-level biography/entity summary frame (currently for persons).

These are defined in `semantics/types.py` and should be treated as the **source of truth** for field names and basic behavior.

### 2.2 Frame protocol and naming

All frames follow the common `Frame` protocol:

```python
from typing import Protocol

class Frame(Protocol):
    frame_type: str  # e.g. "bio", "entity.organization"
````

Design rules:

* Every concrete frame has:

  * A **Python class name** (e.g. `OrgFrame`).
  * A **canonical `frame_type` string** (e.g. `"entity.organization"`).

* Frame type strings use the pattern:

  * `bio.person` or `bio` for biography-style person frames.
  * `entity.<subtype>` for entity articles.
  * `event.<subtype>` for event frames (see `FRAMES_EVENT`).
  * Higher-level specializations can add more dots, e.g. `entity.organization.sports_team`.

### 2.3 Field categories

For each frame we distinguish:

* **Core identity fields** – minimally needed to say “X is a Y”:

  * the main `Entity` or equivalent (`main_entity`, `subject`),
  * primary type / classification,
  * optionally a canonical label or alias.

* **Infobox-style fields** – high-salience facts that often appear in the first sentence:

  * dates (founding, release, signing),
  * location (headquarters, setting),
  * key roles (founder, director, author, stars),
  * scale measures (population, runtime, capacity, revenue, number of speakers).

* **Attribute map** – loose key → value store:

  ```python
  attributes: dict[str, Any]
  ```

  Used to attach domain-specific facts without exploding the dataclass field list.

* **Events** – where appropriate, we attach important events as `Event` objects:

  * birth/death events for persons,
  * founding/dissolution events for organizations,
  * signing/coming-into-force for treaties,
  * etc.

### 2.4 Minimal vs enriched frames

Each frame definition specifies:

* A **minimal required subset**, sufficient to generate a basic “X is a Y” sentence.
* Additional **optional fields** that improve richness and accuracy.

Importantly, **bridges must not assume optional fields are present**. Engines and constructions must degrade gracefully.

---

## 3. Inventory of entity frame families

The current planned entity frame families are:

| ID | Frame family                             | Canonical `frame_type` example | Typical subjects                              |
| -- | ---------------------------------------- | ------------------------------ | --------------------------------------------- |
| 1  | Person / biography                       | `bio` / `bio.person`           | Humans, historical figures, fictional persons |
| 2  | Organization / group                     | `entity.organization`          | Companies, NGOs, parties, bands               |
| 3  | Geopolitical entity                      | `entity.gpe`                   | Countries, states, municipalities             |
| 4  | Other place / geographic feature         | `entity.place`                 | Mountains, rivers, regions, parks             |
| 5  | Facility / infrastructure                | `entity.facility`              | Buildings, stations, stadiums, bridges        |
| 6  | Astronomical object                      | `entity.astronomical_object`   | Planets, stars, galaxies, exoplanets          |
| 7  | Species / taxon                          | `entity.taxon`                 | Species, genera, families, etc.               |
| 8  | Chemical / material                      | `entity.chemical`              | Chemical elements, compounds, materials       |
| 9  | Physical object / artifact               | `entity.artifact`              | Tools, weapons, devices, art objects          |
| 10 | Vehicle / craft                          | `entity.vehicle`               | Ships, aircraft, trains, spacecraft           |
| 11 | Creative work                            | `entity.creative_work`         | Books, films, albums, games, paintings        |
| 12 | Software / website / protocol / standard | `entity.software_or_standard`  | Software, websites, protocols, standards      |
| 13 | Product / brand                          | `entity.product_or_brand`      | Consumer products, brands, product lines      |
| 14 | Sports team / club                       | `entity.sports_team`           | Clubs, franchises, national teams             |
| 15 | Competition / tournament / league        | `entity.competition`           | Leagues, cups, championships, seasons         |
| 16 | Language                                 | `entity.language`              | Natural languages, conlangs, dialects         |
| 17 | Religion / belief system / ideology      | `entity.belief_system`         | Religions, denominations, ideologies          |
| 18 | Academic discipline / field / theory     | `entity.academic_discipline`   | Fields (topology), theories (relativity)      |
| 19 | Law / treaty / policy / constitution     | `entity.law_or_treaty`         | Statutes, treaties, constitutions, policies   |
| 20 | Project / program / initiative           | `entity.project_or_program`    | Missions, campaigns, research projects        |
| 21 | Fictional entity / universe / franchise  | `entity.fictional`             | Characters, settings, franchises, universes   |

Each of these corresponds to a **family**: multiple concrete subtypes (e.g. `entity.organization.sports_team`) can share the same basic frame schema with slightly different conventions.

---

## 4. Common schema pattern

Most entity frames follow a shared skeleton:

```python
from dataclasses import dataclass, field
from typing import Any, Optional

from semantics.types import Entity, Event, Location, TimeSpan  # existing types

@dataclass
class BaseEntityFrame:
    """
    Common base for entity-centric frames.
    Not necessarily a real superclass in code, but a conceptual template.
    """

    frame_type: str
    main_entity: Entity                 # the thing the article is about
    entity_role: str = "subject"        # optional semantic role label
    attributes: dict[str, Any] = field(default_factory=dict)
    key_events: list[Event] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)
```

Individual frames typically:

* Fix `frame_type` to a constant.
* Add a small set of **typed fields** for their domain.
* Use `attributes` and `extra` for everything else.

---

## 5. Frame-by-frame specifications

For each family:

* “Core fields” = recommended explicit dataclass fields.
* “Attributes keys” = typical keys in the generic `attributes` map.

### 5.1 Person / biography (`bio` / `bio.person`)

**Implementation note:** Currently handled by `semantics.types.BioFrame` and `Entity`. The rest of the document is compatible with that design.

#### Core fields

* `frame_type: str = "bio"` (or `"bio.person"` in future)

* `main_entity: Entity`

  * `entity_type` should be `"person"`.
  * `human` should be `True`.

* `primary_profession_lemmas: list[str]`

  * Lemmas like `"physicist"`, `"writer"`, `"politician"`.

* `nationality_lemmas: list[str]`

  * Lemmas like `"polish"`, `"Kenyan"`, `"Brazilian"`.

* `birth_event: Event | None`

  * `event_type = "birth"`.
  * `participants["subject"] = main_entity`.

* `death_event: Event | None`

  * `event_type = "death"`.

* `other_events: list[Event]`

  * `event_type` values like `"award"`, `"appointment"`, `"discovery"`, `"office_holding"`.

#### Attributes keys

Typical keys in `attributes`:

* `field: list[str]` – disciplines or specialties.
* `known_for: list[str]` – key works or achievements.
* `positions: list[dict]` – office holding (role, org, time).
* `awards: list[dict]` – award name, year.
* `education: list[dict]` – institutions, degrees.
* `membership: list[dict]` – parties, organizations.

#### Minimal frame

For a bare “X is a Y” biography:

* `main_entity` (with `name`, `gender`, `human=True`).
* At least one `primary_profession_lemmas` entry.

Example:

```python
from semantics.types import Entity, BioFrame

bio = BioFrame(
    main_entity=Entity(name="Marie Curie", gender="female", human=True),
    primary_profession_lemmas=["physicist", "chemist"],
    nationality_lemmas=["polish", "french"],
)
```

---

### 5.2 Organization / group (`entity.organization`)

Covers companies, NGOs, political parties, bands, clubs, informal groups.

#### Core fields

* `frame_type: str = "entity.organization"`

* `main_entity: Entity`

  * `entity_type` should be `"organization"` (or a more specific subtype).

* `org_kind: str | None`

  * e.g. `"company"`, `"political party"`, `"ngo"`, `"trade union"`, `"band"`.

* `founded_event: Event | None`

  * `event_type = "founding"`.

* `dissolved_event: Event | None`

  * `event_type = "dissolution"`.

* `headquarters: Location | None`

* `membership_size: int | None`

* `industry_or_sector: list[str]`

* `parent_org: Entity | None`

* `subsidiaries: list[Entity]`

#### Attributes keys

* `founders: list[Entity]`
* `key_people: list[Entity]` – CEOs, chairs, leaders.
* `products: list[Entity]` – for companies.
* `ideology: list[str]` – for parties/movements.
* `affiliations: list[Entity]` – alliances, federations.
* `website: str`
* `stock_tickers: list[str]`

---

### 5.3 Geopolitical entity (`entity.gpe`)

Countries, states, provinces, cities, municipalities, dependencies.

#### Core fields

* `frame_type: str = "entity.gpe"`

* `main_entity: Entity`

  * `entity_type` values like `"country"`, `"city"`, `"province"`.

* `gpe_kind: str` – `"country"`, `"province"`, `"region"`, `"city"`, `"municipality"`, etc.

* `sovereign_state: Entity | None`

  * For subnational entities or dependencies.

* `capital: Entity | None` – reference to a city entity.

* `population: int | None`

* `area_km2: float | None`

* `official_languages: list[str]`

* `timezones: list[str]`

#### Attributes keys

* `government_type: str`
* `currency: str`
* `demonym_lemmas: list[str]` – e.g. `"French"`, `"Kenyan"`.
* `iso_codes: dict` – e.g. `{"alpha2": "FR", "numeric": "250"}`.
* `gdp_nominal: dict` – value, year, currency.
* `gdp_ppp: dict`
* `subdivisions: list[Entity]`

---

### 5.4 Other place / geographic feature (`entity.place`)

Mountains, rivers, lakes, seas, islands, regions, parks, etc.

#### Core fields

* `frame_type: str = "entity.place"`

* `main_entity: Entity`

* `place_kind: str`

  * `"mountain"`, `"river"`, `"lake"`, `"island"`, `"sea"`, `"desert"`, `"national park"`, etc.

* `located_in: list[Entity]`

  * Higher-level regions/countries.

* `coords: dict | None`

  * e.g. `{"lat": 48.8584, "lon": 2.2945}`.

* `area_km2: float | None`

* `elevation_m: float | None`

* `length_km: float | None` (for rivers).

#### Attributes keys

* `source_location: Location` – rivers.
* `mouth_location: Location`
* `peak_elevation_m: float` – mountains.
* `protected_status: str` – for parks.

---

### 5.5 Facility / infrastructure (`entity.facility`)

Buildings, airports, stations, stadiums, bridges, dams, power plants.

#### Core fields

* `frame_type: str = "entity.facility"`

* `main_entity: Entity`

* `facility_kind: str`

  * `"airport"`, `"railway station"`, `"stadium"`, `"bridge"`, `"dam"`, `"power plant"`, etc.

* `location: Location`

* `owner_or_operator: Entity | None`

* `capacity: int | None` – passengers per year, seats, MW, etc.

* `opened_event: Event | None`

* `closed_event: Event | None`

#### Attributes keys

* `architects: list[Entity]`
* `lines_served: list[Entity]` – for stations.
* `surface: str` – e.g. grass, artificial turf.
* `height_m: float`
* `span_m: float` – for bridges.

---

### 5.6 Astronomical object (`entity.astronomical_object`)

Planets, stars, galaxies, exoplanets, minor planets, moons, nebulae.

#### Core fields

* `frame_type: str = "entity.astronomical_object"`

* `main_entity: Entity`

* `astro_kind: str`

  * `"star"`, `"planet"`, `"moon"`, `"galaxy"`, `"nebula"`, `"asteroid"`, etc.

* `mass_kg: float | None`

* `radius_km: float | None`

* `orbital_period_days: float | None` – for orbiting bodies.

* `semi_major_axis_au: float | None`

* `distance_ly: float | None`

* `constellation: str | None` – for stars.

#### Attributes keys

* `discovery_event: Event` – includes discoverer, date.
* `spectral_type: str`
* `host_star: Entity` – for exoplanets.
* `satellites: list[Entity]`

---

### 5.7 Species / taxon (`entity.taxon`)

Biological taxa at any rank.

#### Core fields

* `frame_type: str = "entity.taxon"`

* `main_entity: Entity`

  * `name` should be the scientific name where applicable.

* `rank: str`

  * `"species"`, `"genus"`, `"family"`, `"order"`, etc.

* `parent_taxon: Entity | None`

* `common_names: list[str]`

* `distribution_regions: list[Entity]` – continents, countries.

* `conservation_status: str | None`

  * `"LC"`, `"EN"`, `"CR"`, etc. or full labels.

#### Attributes keys

* `habitats: list[str]`
* `diet: list[str]`
* `average_lifespan_years: float`
* `average_length_cm: float`
* `average_weight_kg: float`
* `iucn_system_version: str`

---

### 5.8 Chemical / material (`entity.chemical`)

Individual chemical substances or classes of materials.

#### Core fields

* `frame_type: str = "entity.chemical"`

* `main_entity: Entity`

* `formula: str | None`

* `iupac_name: str | None`

* `cas_number: str | None`

* `state_at_stp: str | None`

  * `"solid"`, `"liquid"`, `"gas"`.

* `melting_point_c: float | None`

* `boiling_point_c: float | None`

* `density_g_cm3: float | None`

#### Attributes keys

* `hazard_statements: list[str]`
* `uses: list[str]`
* `solubility: dict` – solvent → qualitative/quantitative measure.
* `production_volume_tonnes_per_year: float`

---

### 5.9 Physical object / artifact (`entity.artifact`)

Individual artifacts or generic object types.

#### Core fields

* `frame_type: str = "entity.artifact"`

* `main_entity: Entity`

* `artifact_kind: str`

  * `"sword"`, `"painting"`, `"tool"`, `"machine"`, `"instrument"`.

* `creator_or_maker: Entity | None`

* `creation_timespan: TimeSpan | None`

* `materials: list[str]`

* `current_location: Location | None`

* `dimensions: dict | None`

  * e.g. `{ "height_cm": 50, "width_cm": 30 }`.

#### Attributes keys

* `collection: Entity` – museum, gallery.
* `inscriptions: list[str]`
* `provenance: list[dict]` – previous owners, dates.

> Note: paintings and other artworks may instead use `entity.creative_work` with a `work_kind` like `"painting"`. Which frame to use depends on whether the article focuses on the **work as a text/film** or **the physical object**.

---

### 5.10 Vehicle / craft (`entity.vehicle`)

Ships, aircraft, trains, spacecraft, car models, classes of vehicles.

#### Core fields

* `frame_type: str = "entity.vehicle"`

* `main_entity: Entity`

* `vehicle_kind: str`

  * `"ship"`, `"aircraft"`, `"train"`, `"locomotive"`, `"spacecraft"`, `"car model"`, etc.

* `manufacturer: Entity | None`

* `operator: Entity | None`

* `entered_service: Event | None`

* `retired_from_service: Event | None`

* `crew_capacity: int | None`

* `passenger_capacity: int | None`

* `displacement_tonnes: float | None` – ships.

* `mass_kg: float | None`

* `top_speed_kmh: float | None`

* `range_km: float | None`

#### Attributes keys

* `registration_numbers: list[str]`
* `callsign: str`
* `class: str` – e.g. `"Nimitz-class aircraft carrier"`.

---

### 5.11 Creative work (`entity.creative_work`)

Books, films, TV shows, episodes, albums, songs, comics, games, artworks.

#### Core fields

* `frame_type: str = "entity.creative_work"`

* `main_entity: Entity`

* `work_kind: str`

  * `"novel"`, `"film"`, `"television series"`, `"album"`, `"song"`, `"painting"`, `"video game"`, etc.

* `creator_entities: list[Entity]`

  * Authors, directors, composers, artists, designers.

* `release_event: Event | None`

  * `event_type = "release"`; time and place as appropriate.

* `original_language: str | None`

* `runtime_minutes: int | None` – films, episodes.

* `page_count: int | None` – books.

* `episode_count: int | None` – TV series.

* `series_or_franchise: Entity | None`

#### Attributes keys

* `genre_lemmas: list[str]`
* `publisher_or_label: Entity`
* `cast: list[dict]` – actor entity + role.
* `platforms: list[str]` – games.
* `awards: list[dict]` – award name, year.

---

### 5.12 Software / website / protocol / standard (`entity.software_or_standard`)

Software packages, websites, internet protocols, standards.

#### Core fields

* `frame_type: str = "entity.software_or_standard"`

* `main_entity: Entity`

* `artifact_kind: str`

  * `"software"`, `"website"`, `"protocol"`, `"standard"`, etc.

* `developer_or_maintainer: list[Entity]`

* `initial_release_event: Event | None`

* `latest_release_version: str | None`

* `latest_release_time: TimeSpan | None`

* `license: str | None`

* `platforms: list[str]`

* `supported_protocols_or_standards: list[str]`

#### Attributes keys

* `website: str`
* `repository_url: str`
* `programming_languages: list[str]`
* `osi_approved: bool`

---

### 5.13 Product / brand (`entity.product_or_brand`)

Commercial products, product lines, brands.

#### Core fields

* `frame_type: str = "entity.product_or_brand"`

* `main_entity: Entity`

* `product_kind: str`

  * `"soft drink"`, `"car model"`, `"smartphone"`, `"clothing brand"`, etc.

* `manufacturer_or_owner: Entity | None`

* `launch_event: Event | None`

* `discontinued_event: Event | None`

* `markets: list[Entity]` – countries or regions where available.

#### Attributes keys

* `variants: list[dict]` – versions, flavors, trims.
* `slogans: list[str]`
* `parent_brand: Entity`

---

### 5.14 Sports team / club (`entity.sports_team`)

Clubs, franchises, national teams.

#### Core fields

* `frame_type: str = "entity.sports_team"`
* `main_entity: Entity`
* `sport: str`
* `league_or_competition: Entity | None`
* `location: Location` – city, region.
* `home_venue: Entity | None` – stadium, arena.
* `founded_event: Event | None`
* `dissolved_event: Event | None`

#### Attributes keys

* `nicknames: list[str]`
* `colors: list[str]`
* `head_coach_or_manager: Entity | None`
* `captains: list[Entity]`
* `major_titles: list[dict]` – competition, seasons.

---

### 5.15 Competition / tournament / league (`entity.competition`)

Leagues, recurring tournaments, championships, seasons.

#### Core fields

* `frame_type: str = "entity.competition"`

* `main_entity: Entity`

* `competition_kind: str`

  * `"league"`, `"cup"`, `"tournament"`, `"championship"`, `"season"`.

* `sport: str`

* `organizing_body: Entity | None`

* `founded_event: Event | None`

* `number_of_teams_or_participants: int | None`

* `season_structure: dict | None` – regular season, playoffs.

#### Attributes keys

* `current_champions: Entity | None`
* `most_successful_clubs: list[Entity]`
* `promotion_relegation_system: str`

---

### 5.16 Language (`entity.language`)

Natural languages, constructed languages, dialects, sign languages.

#### Core fields

* `frame_type: str = "entity.language"`

* `main_entity: Entity`

* `language_kind: str`

  * `"natural"`, `"constructed"`, `"sign"`, `"creole"`, etc.

* `language_family: Entity | None`

* `iso_codes: dict | None`

  * e.g. `{"iso_639_1": "fr", "iso_639_3": "fra"}`.

* `number_of_speakers: int | None`

* `regions: list[Entity]`

* `writing_systems: list[str]`

#### Attributes keys

* `official_status: list[dict]` – country, level of official status.
* `dialects: list[Entity]`
* `typology: dict` – word order, morphology type.

---

### 5.17 Religion / belief system / ideology (`entity.belief_system`)

Religions, denominations, philosophies, political ideologies.

#### Core fields

* `frame_type: str = "entity.belief_system"`

* `main_entity: Entity`

* `belief_kind: str`

  * `"religion"`, `"denomination"`, `"philosophy"`, `"political ideology"`.

* `origin_place: Location | None`

* `origin_timespan: TimeSpan | None`

* `founder_entities: list[Entity]`

* `primary_texts: list[Entity]`

#### Attributes keys

* `core_beliefs: list[str]`
* `denominations_or_branches: list[Entity]`
* `number_of_adherents: int | None`
* `regions: list[Entity]`

---

### 5.18 Academic discipline / field / theory (`entity.academic_discipline`)

Disciplines, subfields, major theories.

#### Core fields

* `frame_type: str = "entity.academic_discipline"`

* `main_entity: Entity`

* `discipline_kind: str`

  * `"discipline"`, `"subdiscipline"`, `"theory"`, `"hypothesis"`.

* `parent_discipline: Entity | None`

* `related_fields: list[Entity]`

#### Attributes keys

* `applications: list[str]`
* `notable_figures: list[Entity]`
* `major_concepts: list[str]`
* `founding_period: TimeSpan | None`

---

### 5.19 Law / treaty / policy / constitution (`entity.law_or_treaty`)

Statutes, treaties, constitutions, major policies.

#### Core fields

* `frame_type: str = "entity.law_or_treaty"`

* `main_entity: Entity`

* `instrument_kind: str`

  * `"treaty"`, `"law"`, `"constitution"`, `"policy"`.

* `jurisdiction: Entity | None`

* `signing_event: Event | None`

* `coming_into_force_event: Event | None`

* `repeal_event: Event | None`

* `status: str` – `"in force"`, `"repealed"`, etc.

#### Attributes keys

* `parties: list[Entity]` – for treaties.
* `subjects: list[str]`
* `articles_or_sections: list[str]` – identifiers only.
* `legal_citations: list[str]`

---

### 5.20 Project / program / initiative (`entity.project_or_program`)

Government programs, research projects, campaigns, missions.

#### Core fields

* `frame_type: str = "entity.project_or_program"`

* `main_entity: Entity`

* `project_kind: str`

  * `"space mission"`, `"research program"`, `"campaign"`, `"initiative"`.

* `sponsors_or_organizations: list[Entity]`

* `start_timespan: TimeSpan | None`

* `end_timespan: TimeSpan | None`

* `budget: dict | None`

  * value, currency, reference year.

#### Attributes keys

* `objectives: list[str]`
* `outcomes: list[str]`
* `participants: list[Entity]`
* `missions_or_phases: list[dict]`

---

### 5.21 Fictional entity / universe / franchise (`entity.fictional`)

Fictional characters, settings, universes, franchises.

#### Core fields

* `frame_type: str = "entity.fictional"`

* `main_entity: Entity`

* `fictional_kind: str`

  * `"character"`, `"location"`, `"organization"`, `"universe"`, `"franchise"`.

* `source_works: list[Entity]`

* `creators: list[Entity]`

* `appears_in_works: list[Entity]`

#### Attributes keys

* `abilities_or_powers: list[str]` – characters.
* `affiliations: list[Entity]`
* `species: Entity | None`
* `timeline_information: list[str]`

---

## 6. Construction and engine implications

Entity frames interact with the rest of the system as follows:

1. **Input:** A frontend (e.g. an AW/Z bridge) constructs an appropriate entity frame, using `Entity`, `Event`, `Location`, `TimeSpan` objects where needed.

2. **Planning:** A discourse planner or simple heuristic picks:

   * Which entity frames (and possibly event frames) to use in the lead.
   * The order in which they should appear.

3. **Construction selection:** Based on `frame_type` and available fields, the engine chooses:

   * Equative constructions (`X is a Y`) for definitions.
   * Locative constructions (`X is in Y`) for locations.
   * Possessive constructions (`X has Y`) for capacities, members, etc.

4. **Morphology & realization:** Engines and constructions use generic roles (subject, predicate NP, location, etc.) plus feature maps from the frames to realize language-specific sentences.

When adding a new entity-frame implementation:

* Follow the **core pattern** in §4.
* Keep the number of explicit fields **small and stable**; prefer attribute maps for long-tail facts.
* Ensure `frame_type` is **unique and descriptive**.
* Make it easy to **downgrade** to a simpler frame if data is sparse (e.g., an `entity.organization` with only `main_entity` and `org_kind` should still render a simple definition).

---

## 7. Incremental implementation strategy

Given that only `BioFrame` is currently wired end-to-end, a pragmatic rollout plan is:

1. Implement dataclasses and normalization for **`entity.organization`** and **`entity.gpe`**, as they cover a large share of entity articles.
2. Add **`entity.creative_work`** and **`entity.language`**.
3. Gradually add domain-specific frames where needed, reusing:

   * `Entity` for core identity,
   * `Event` for major milestones,
   * attribute maps for long-tail features.

Each new frame should be accompanied by:

* A test corpus (small) demonstrating:

  * minimal input → simple lead sentence,
  * richer input → more informative sentences.

* Construction / engine rules for the initial supported families.

---

## 8. Summary

* Entity frames model **article subjects** across domains.
* They build on the core semantic types (`Entity`, `Location`, `TimeSpan`, `Event`) and follow a common `Frame` protocol.
* `BioFrame` already implements the **person** case; this document generalizes that idea to 20 additional entity families.
* Implementations are kept **compact** (few explicit fields) plus an `attributes` map for extensibility.
* The `frame_type` taxonomy (`bio.person`, `entity.organization`, `entity.gpe`, `entity.academic_discipline`, `entity.law_or_treaty`, etc.) is the primary hook for:

  * mapping AW/Z data into frames,
  * routing frames to appropriate constructions and engines.

