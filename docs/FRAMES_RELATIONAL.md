
# Relational frames (statement-level frames)

This document specifies the **relational / statement-level frames** used to express simple facts about entities and events:

* Definition / classification
* Attributes and properties
* Quantities and measurements
* Comparisons and rankings
* Membership, roles, ownership, part–whole
* Spatial / temporal / causal relations
* Communications and opinions
* Small bundles of related facts

Relational frames are:

* **Language-independent:** they live in `semantics/` and are consumed by engines + constructions.
* **Small and compositional:** each frame encodes one “fact pattern”.
* **Reusable:** they can be embedded in higher-level frames (bios, events, entity summaries) or used standalone.

The intention is that higher-level frames (e.g. `BioFrame`, entity frames) will contain **lists of relational frames** to drive many of their sentences.

---

## 1. Conventions and common helper types

### 1.1 Where these live

Recommended location for the concrete Python types:

```text
semantics/types.py                 # core dataclasses (Entity, TimeSpan, Event, BioFrame, …)
semantics/common/quantity.py       # Quantity helper
semantics/relational/*.py          # concrete relational frame dataclasses
schemas/frames/relational_*.json   # JSON schemas for validation / public API
````

This document is the **schema**; the exact module layout is an implementation detail.

### 1.2 Common helper types

All relational frames assume the following basic types from `semantics.types`:

```python
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from semantics.types import Entity, Event, TimeSpan
```

Where:

* `Entity`: person, organization, place, abstract thing, etc.
* `Event`: semantic event or state.
* `TimeSpan`: coarse date / time interval.

### 1.3 Quantity helper

Many relational frames need numeric values. Use a small helper dataclass:

```python
@dataclass
class Quantity:
    """
    A numeric quantity with optional unit and bounds.

    Examples:
        - 3.5 million inhabitants
        - 42 km
        - between 10 and 20 °C (approximate)
    """
    value: float
    unit: str = ""                # "people", "km", "USD", "°C", "points", …
    approximate: bool = False     # True → "about", "roughly"
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None
    time: Optional[TimeSpan] = None
    extra: Dict[str, Any] = field(default_factory=dict)
```

In the codebase this lives in `semantics/common/quantity.py`; the definition above is included here for reference.

### 1.4 Common fields for all relational frames

Every relational frame MAY include:

```python
id: Optional[str]            # stable identifier (e.g. for merging / cross-ref)
source_id: Optional[str]     # provenance, e.g. Wikidata statement ID, AW node
time: Optional[TimeSpan]     # when the fact holds / was measured
certainty: float = 1.0       # 0.0–1.0, optional
extra: Dict[str, Any]        # open-ended metadata from upstream
```

Not all frames need all of these; they are provided as a shared pattern.

---

## 2. Core relational frame families

Below, each subsection defines:

* **Intended meaning / usage**
* **Minimal field set**
* **Typical mapping to constructions**

Field types follow the helpers above.

---

### 2.1 Definition / classification (`DefinitionFrame`)

“X is a Y (Z).” / “X is a French physicist.”

**Purpose**

Classify an entity into one or more types/supertypes, optionally with modifiers. This covers:

* Simple definitions (“X is a river.”)
* Multi-label types (“X is a French physicist and chemist.”)
* Basic ontological relations (“X is a city in Y.” – the location part can combine with a spatial frame).

**Dataclass**

```python
@dataclass
class DefinitionFrame:
    """
    Definition / classification: "X is a Y (Z)".

    Examples:
        - "Marie Curie was a Polish physicist and chemist."
        - "The Amazon is a river in South America."
    """
    id: Optional[str] = None

    subject: Entity                     # X
    # One or more type labels. For many domains these will ultimately
    # come from lexemes / lemmas ("physicist", "river") rather than
    # full Entities.
    type_lemmas: List[str] = field(default_factory=list)

    # Optional “higher” categories, for ontological statements:
    #   "X is a city in the Italian region of Piedmont."
    supertype_entities: List[Entity] = field(default_factory=list)

    # Free-form modifiers like nationality, field, etc.,
    # if they are not separately modeled as attributes.
    modifiers: Dict[str, Any] = field(default_factory=dict)

    time: Optional[TimeSpan] = None     # when the definition holds, if relevant
    certainty: float = 1.0
    source_id: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)
```

**Typical mapping**

* `constructions/copula_equative_classification.py`
* SUBJ = subject, PRED_NP built from `type_lemmas` + `modifiers`.

---

### 2.2 Attribute / property (`AttributeFrame`)

“X is ADJ.” / “X has property P = V.”

**Purpose**

Attach a simple (often adjectival) property to a subject:

* “X is democratic.”
* “The river is navigable.”
* “The team is professional.”

**Dataclass**

```python
@dataclass
class AttributeFrame:
    """
    Simple attribute statement.

    Examples:
        - "The party is democratic."
        - "The river is navigable."
        - "The city is bilingual."
    """
    id: Optional[str] = None

    subject: Entity                   # X
    # Coarse attribute category, e.g. "political_system", "status".
    attribute: str
    # Canonical value, e.g. "democratic", "bilingual", "navigable".
    value: Any

    # Optional lexical hints (adjective lemma, NP lemma, etc.)
    value_lemma: Optional[str] = None
    realization_hint: Optional[str] = None  # "adjective", "np", …

    time: Optional[TimeSpan] = None
    certainty: float = 1.0
    source_id: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)
```

**Typical mapping**

* `constructions/copula_attributive_adj.py` or `copula_attributive_np.py`.

---

### 2.3 Quantitative measure (`QuantitativeFrame`)

“At time T, X had population N.” / “X covers area N km².”

**Purpose**

Express 1D numeric facts:

* Populations, areas, distances
* GDP, scores, counts, etc.

**Dataclass**

```python
@dataclass
class QuantitativeFrame:
    """
    Quantitative measurement for a subject.

    Examples:
        - "As of 2020, the population was about 3.5 million."
        - "The river is 640 km long."
    """
    id: Optional[str] = None

    subject: Entity              # X
    measure_type: str            # "population", "area", "length", "gdp", …
    quantity: Quantity           # value, unit, approximate, time

    # Scope / qualifier, e.g. "city proper", "metro area"
    scope: Optional[str] = None

    # How this should be verbalized, if non-default:
    realization_hint: Optional[str] = None  # "as_of_clause", "parenthetical", …

    certainty: float = 1.0
    source_id: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)
```

**Typical mapping**

* Often bundled into **relation bundles** or **timelines**, but basic realization can use:

  * `constructions/copula_attributive_np.py` + prepositional “with …”.

---

### 2.4 Comparative / ranking (`ComparativeFrame`)

“X is larger than Y.” / “X is the second-largest city in Z.”

**Purpose**

Capture comparative and ranking facts over a property.

**Dataclass**

```python
@dataclass
class ComparativeFrame:
    """
    Comparative / superlative statements.

    Examples:
        - "X is larger than Y."
        - "X is the largest city in Z."
        - "X is the second-oldest university in the country."
    """
    id: Optional[str] = None

    subject: Entity                  # X
    property: str                    # "population", "area", "age", …
    comparison_type: str             # "comparative" | "superlative" | "ranking"

    # Comparative:
    standard: Optional[Entity] = None      # Y in "larger than Y"
    direction: str = "greater"             # "greater" | "less"

    # Superlative / ranking:
    rank: Optional[int] = None             # 1, 2, 3, …
    domain: Optional[Entity] = None        # set/domain: country, region, league
    domain_scope: Optional[str] = None     # "in", "among", "within"

    # Optional explicit numeric data, if available:
    subject_quantity: Optional[Quantity] = None
    standard_quantity: Optional[Quantity] = None

    time: Optional[TimeSpan] = None
    certainty: float = 1.0
    source_id: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)
```

**Typical mapping**

* `constructions/comparative_superlative.py` (comparee, standard, domain, etc.).

---

### 2.5 Membership / affiliation (`MembershipFrame`)

“X is a member of Y.” / “X plays for Y.” / “X belongs to party Y.”

**Purpose**

Represent membership / affiliation relations that are not full-blown roles (for those, see RoleFrame).

**Dataclass**

```python
@dataclass
class MembershipFrame:
    """
    Group membership or affiliation.

    Examples:
        - "She is a member of the Academy."
        - "He plays for FC Barcelona."
        - "She belongs to the Green Party."
    """
    id: Optional[str] = None

    member: Entity                 # X
    group: Entity                  # Y
    relation_type: str = "member"  # "member", "player", "supporter", …

    # Optional more specific role label, e.g. "goalkeeper"
    role_label: Optional[str] = None

    start: Optional[TimeSpan] = None
    end: Optional[TimeSpan] = None

    status: Optional[str] = None   # "current", "former", "honorary"
    certainty: float = 1.0
    source_id: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)
```

**Typical mapping**

* Copular or simple eventive constructions, e.g. `copula_attributive_np` + PP “for Y”, or `transitive_event` (“X joined Y”).

---

### 2.6 Role / position / office (`RoleFrame`)

“X served as Y of Z from A to B.”

**Purpose**

Capture more structured office/role-holding relations:

* Political offices
* Academic / corporate positions
* Sports team positions when term-like

**Dataclass**

```python
@dataclass
class RoleFrame:
    """
    Role / office holding.

    Examples:
        - "She served as Prime Minister of X from 2010 to 2015."
        - "He was professor of physics at Y University."
    """
    id: Optional[str] = None

    holder: Entity                      # person
    title_lemma: str                    # "prime minister", "president", "professor"
    organization: Optional[Entity] = None   # government, university, club
    jurisdiction: Optional[Entity] = None   # country, region, department, …

    start: Optional[TimeSpan] = None
    end: Optional[TimeSpan] = None

    # Optional succession info
    predecessor: Optional[Entity] = None
    successor: Optional[Entity] = None

    acting: bool = False
    status: Optional[str] = None        # "current", "former"

    certainty: float = 1.0
    source_id: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)
```

**Typical mapping**

* Copular equatives with PRED_NP built from title + organization/jurisdiction.
* Event-level representations (appointments) can embed or be derived from this.

---

### 2.7 Part–whole / composition (`PartWholeFrame`)

“X is part of Y.” / “Y consists of X and Z.”

**Purpose**

Represent compositional structure:

* Administrative divisions
* Components of an organization
* Physical / conceptual parts

**Dataclass**

```python
@dataclass
class PartWholeFrame:
    """
    Part–whole relationship.

    Examples:
        - "Paris is part of the Île-de-France region."
        - "The team is one of the founding clubs of the league."
        - "The parliament consists of two chambers."
    """
    id: Optional[str] = None

    whole: Entity                     # Y
    part: Entity                      # X
    relation_type: str = "part_of"    # "part_of", "member_of", "component_of", …

    # Optional quantity info:
    share: Optional[Quantity] = None  # e.g. % of area / population
    rank_within_whole: Optional[int] = None  # e.g. "one of ten", "second largest"

    time: Optional[TimeSpan] = None
    certainty: float = 1.0
    source_id: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)
```

**Typical mapping**

* Copular or possessive constructions (“X is part of Y”, “Y includes X”).

---

### 2.8 Ownership / control (`OwnershipFrame`)

“X owns Y.” / “X operates Y.” / “X controls Y.”

**Purpose**

Capture ownership, operation, and control relations for assets, companies, facilities, etc.

**Dataclass**

```python
@dataclass
class OwnershipFrame:
    """
    Ownership / control / operation.

    Examples:
        - "The company owns the stadium."
        - "The state controls the central bank."
        - "The airline operates the route."
    """
    id: Optional[str] = None

    owner: Entity                   # X
    asset: Entity                   # Y
    relation_type: str = "owner"    # "owner", "controller", "operator", …

    # Optional share info:
    share: Optional[Quantity] = None   # e.g. percentage ownership

    start: Optional[TimeSpan] = None
    end: Optional[TimeSpan] = None

    certainty: float = 1.0
    source_id: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)
```

**Typical mapping**

* Transitives: `TRANSITIVE_EVENT`-style (“X owns Y”), or copular possessives (“Y is owned by X”).

---

### 2.9 Spatial relation (`SpatialRelationFrame`)

“X is located in Y.” / “X lies north of Y.”

**Purpose**

Encode simple spatial relations:

* Inclusion (“in”, “inside”)
* Relative position (“north of”, “near”)
* Distance when needed

**Dataclass**

```python
@dataclass
class SpatialRelationFrame:
    """
    Spatial relationship between entities/places.

    Examples:
        - "The city is located in northern Italy."
        - "The river flows through the city."
        - "The island lies 50 km off the coast."
    """
    id: Optional[str] = None

    subject: Entity                       # X
    reference: Entity                     # Y (country, region, other place)
    relation: str                         # "in", "within", "near", "north_of", "on", …

    # Optional quantitative detail:
    distance: Optional[Quantity] = None
    region_lemma: Optional[str] = None    # "northern", "southern", "central", …

    time: Optional[TimeSpan] = None
    certainty: float = 1.0
    source_id: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)
```

**Typical mapping**

* `constructions/copula_locative.py` or eventive constructions with locative roles.

---

### 2.10 Temporal relation (`TemporalRelationFrame`)

“X happened before Y.” / “X has been ongoing since Y.”

**Purpose**

Express relations between times/events:

* Before / after
* Since / until
* During / throughout

**Dataclass**

```python
@dataclass
class TemporalRelationFrame:
    """
    Temporal relationship between events or states.

    Examples:
        - "The war ended before the treaty was signed."
        - "The project has been ongoing since 2010."
        - "The festival takes place every July."
    """
    id: Optional[str] = None

    left: Any                           # Event or Entity or TimeSpan
    right: Any                          # Event or Entity or TimeSpan
    relation: str                       # "before", "after", "since", "until", "during", …

    # Optional explicit spans:
    left_time: Optional[TimeSpan] = None
    right_time: Optional[TimeSpan] = None

    # Recurrence for seasonal / periodic events
    recurrence: Optional[str] = None    # free label, e.g. "annual", "monthly"

    certainty: float = 1.0
    source_id: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)
```

**Typical mapping**

* Temporal adverbials (“since 2010”, “in 1998”), discourse ordering.

---

### 2.11 Causal / influence (`CausalFrame`)

“X caused Y.” / “X led to Y.” / “X contributed to Y.”

**Purpose**

Encode high-level cause–effect or influence relations.

**Dataclass**

```python
@dataclass
class CausalFrame:
    """
    Cause–effect / influence.

    Examples:
        - "The decision caused delays."
        - "The policy led to economic growth."
        - "The discovery contributed to modern physics."
    """
    id: Optional[str] = None

    cause: Any                      # Entity or Event
    effect: Any                     # Entity or Event
    relation: str = "cause"         # "cause", "lead_to", "contribute_to", "trigger", …

    mechanism: Optional[str] = None # short free-text explanation if needed
    strength: Optional[str] = None  # "strong", "weak", "partial"
    certainty: float = 1.0

    time: Optional[TimeSpan] = None
    source_id: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)
```

**Typical mapping**

* `constructions/causative_event.py` (“X caused Y”, “X made Y happen”).

---

### 2.12 Change-of-state (`ChangeOfStateFrame`)

“X became Y.” / “X was abolished.” / “X was converted into Y.”

**Purpose**

Capture transitions of a single entity between states, with optional trigger.

**Dataclass**

```python
@dataclass
class ChangeOfStateFrame:
    """
    Change of state for a subject.

    Examples:
        - "The town became a city in 1905."
        - "The institution was abolished in 1999."
        - "The company was renamed X in 2010."
    """
    id: Optional[str] = None

    subject: Entity                    # X
    old_state: Optional[str] = None    # free label, e.g. "town", old name
    new_state: Optional[str] = None    # free label or lemma
    change_type: str                   # "become", "abolish", "rename", "merge", …

    # Optional trigger / cause:
    trigger_event: Optional[Event] = None
    trigger_description: Optional[str] = None

    time: Optional[TimeSpan] = None
    certainty: float = 1.0
    source_id: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)
```

**Typical mapping**

* Passive / inchoative constructions (“was abolished”, “became X”).

---

### 2.13 Communication / statement (`CommunicationFrame`)

“According to X, Y.” / “X said that …”

**Purpose**

Attach propositional content to a source:

* Direct / indirect quotes
* Attributed claims and reports

**Dataclass**

```python
@dataclass
class CommunicationFrame:
    """
    Attributed statement / communication.

    Examples:
        - "According to historians, the battle was decisive."
        - "The report stated that the project was delayed."
    """
    id: Optional[str] = None

    source: Entity                    # speaker / author / authority
    content: Any                      # proposition, often another frame or small dict
    # High-level type of communication:
    comm_type: str = "statement"      # "statement", "report", "claim", "estimate", …

    # How to attribute:
    medium: Optional[str] = None      # "book", "interview", "press_release"
    audience: Optional[Entity] = None # if relevant
    time: Optional[TimeSpan] = None

    # Optional direct-quote surface, if you want to freeze wording:
    quoted_text: Optional[str] = None

    certainty: float = 1.0            # confidence that the attribution is correct
    source_id: Optional[str] = None   # provenance of the fact "X said content"
    extra: Dict[str, Any] = field(default_factory=dict)
```

**Typical mapping**

* Communication / report constructions, often with optional “According to …”.

---

### 2.14 Opinion / evaluation (`OpinionFrame`)

“X is considered Y.” / “Critics praised X.”

**Purpose**

Represent evaluations that should remain attributed:

* Critical / public opinions
* Assessments, ratings, reputations

**Dataclass**

```python
@dataclass
class OpinionFrame:
    """
    Attributed opinion / evaluation.

    Examples:
        - "The film received positive reviews."
        - "Critics praised the performance."
        - "He is widely regarded as one of the greatest players."
    """
    id: Optional[str] = None

    evaluator: Optional[Entity] = None     # "critics", "scholars", "public", …
    subject: Entity                        # thing being evaluated
    aspect: Optional[str] = None           # "performance", "design", "story", …
    polarity: str = "positive"             # "positive", "negative", "mixed", …

    # Optional scalar rating:
    rating_value: Optional[float] = None
    rating_scale: Optional[str] = None     # "out_of_10", "stars", …

    time: Optional[TimeSpan] = None
    basis: Optional[str] = None            # "reviews", "polls", …

    certainty: float = 1.0                 # how strongly the system believes this statement is supported
    source_id: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)
```

**Typical mapping**

* Copular / passive constructions with evaluative predicates (“is widely regarded as …”).

---

### 2.15 Relation bundle / multi-fact (`RelationBundleFrame`)

“X is a Y in Z with population N.” (pack several simple facts into one or two sentences.)

**Purpose**

Group a small set of relational frames about the same subject into a compact bundle. This is a **planning convenience**:

* Instead of generating 3 separate sentences, the engine can merge them.
* Typical for article leads: type + location + population.

**Dataclass**

```python
@dataclass
class RelationBundleFrame:
    """
    Small bundle of related relational frames about a single subject.

    Used as a planning convenience; individual subframes are still
    valid on their own.
    """
    id: Optional[str] = None

    subject: Entity

    # Arbitrary relational frames concerning `subject`.
    relations: List[Any] = field(default_factory=list)
    # Optional hint for how tightly to bundle things:
    strategy: Optional[str] = None   # "lead_sentence", "compact", "separate_sentences"

    extra: Dict[str, Any] = field(default_factory=dict)
```

**Typical usage**

* A `BioFrame` or entity frame may store:

  * `definition_frames: list[DefinitionFrame]`
  * `quant_frames: list[QuantitativeFrame]`
  * `spatial_frames: list[SpatialRelationFrame]`
  * or directly:
  * `relation_bundles: list[RelationBundleFrame]`

The engine decides how aggressively to merge facts into single sentences vs separate ones.

---

## 3. Integration into higher-level frames and pipeline

1. **Storage inside higher-level frames**

   * Extend `BioFrame` / entity frames with e.g.:

     ```python
     relational_facts: List[Any] = field(default_factory=list)
     ```

     or with typed lists (`definitions`, `quantities`, etc.), depending on how fine-grained you want the API to be.

2. **Normalization**

   * Bridges from AW / Ninai / Wikidata convert loose JSON into these concrete dataclasses.
   * Unknown or extra keys from upstream go into `extra` to avoid information loss.

3. **Routing to constructions**

   * For each relational frame type, engines map it to:

     * a **construction choice** (copular, comparative, causative, etc.), and
     * a **ClauseInput** (roles + features) for that construction.

4. **Discourse and aggregation**

   * `discourse/planner.py` can:

     * order relational frames,
     * decide which to bundle into `RelationBundleFrame`,
     * choose pronouns vs full NPs using `DiscourseState`.

With this inventory, the system can express most of the simple factual content of lead sections and infobox-like statements in a uniform, language-agnostic way.


