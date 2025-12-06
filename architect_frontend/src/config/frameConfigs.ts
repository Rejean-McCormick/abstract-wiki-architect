// architect_frontend/src/config/frameConfigs.ts

// Basic field types used by the generic frame form.
export type FieldType = 'text' | 'textarea' | 'number' | 'select' | 'date';

// Option for select-type fields.
export interface SelectOption {
  value: string;
  label: string;
}

// Configuration for a single logical field in a frame.
export interface FrameFieldConfig {
  // JSON field name in the frame payload.
  name: string;

  // Human-readable label in the UI.
  label: string;

  // Input widget type.
  type: FieldType;

  // Whether this field is required for a “minimal” frame.
  required?: boolean;

  // Placeholder shown in the input.
  placeholder?: string;

  // Helper text shown under the field.
  helpText?: string;

  // Whether the field accepts multiple values (comma-separated in a simple UI).
  multivalue?: boolean;

  // Optional fixed choices (used when type === 'select').
  options?: SelectOption[];
}

// High-level frame family buckets; useful for navigation and filtering.
export type FrameFamily =
  | 'bio'
  | 'entity'
  | 'event'
  | 'rel'
  | 'narr'
  | 'meta';

// Configuration for one “frame context” – a UI surface for a given frame_type.
export interface FrameContextConfig {
  // URL slug under /abstract_wiki_architect/[slug].
  slug: string;

  // Canonical frame_type string used by the backend (router / registry).
  // Examples: "bio", "entity.person", "event.generic", "rel.definition".
  frameType: string;

  // High-level family grouping (bio / entity / event / rel / narr / meta).
  family: FrameFamily;

  // Display title for the workspace.
  title: string;

  // Short description of what this context is for.
  description: string;

  // Default language to preselect in the UI.
  defaultLang?: string;

  // The editable fields exposed in the generic frame form.
  fields: FrameFieldConfig[];
}

// Initial set of supported contexts for the Architect UI.
// This list can be extended as more frames are exposed.
export const FRAME_CONTEXTS: FrameContextConfig[] = [
  {
    slug: 'bio',
    frameType: 'bio',
    family: 'bio',
    title: 'Person biography',
    description:
      'Wikipedia-style lead sentence for a person: who they are, what they do, and key dates.',
    defaultLang: 'en',
    fields: [
      {
        name: 'subject_label',
        label: 'Person label',
        type: 'text',
        required: true,
        placeholder: 'Ada Lovelace',
        helpText:
          'Canonical name or label of the person the biography is about.',
      },
      {
        name: 'primary_professions',
        label: 'Primary profession(s)',
        type: 'text',
        multivalue: true,
        placeholder: 'mathematician, writer',
        helpText:
          'Comma-separated list of profession lemmas: “physicist”, “composer”, …',
      },
      {
        name: 'nationalities',
        label: 'Nationality adjectives',
        type: 'text',
        multivalue: true,
        placeholder: 'British, Polish',
        helpText:
          'Comma-separated list of nationality adjectives to describe the person.',
      },
      {
        name: 'birth_date',
        label: 'Birth date',
        type: 'date',
        helpText: 'Date of birth (if known).',
      },
      {
        name: 'death_date',
        label: 'Death date',
        type: 'date',
        helpText: 'Date of death, if the person is deceased.',
      },
      {
        name: 'known_for',
        label: 'Known for',
        type: 'textarea',
        placeholder: 'Work on the Analytical Engine; early computer science.',
        helpText:
          'Short neutral summary of notable achievements or reasons for notability.',
      },
    ],
  },
  {
    slug: 'entity-organization',
    frameType: 'entity.organization',
    family: 'entity',
    title: 'Organization / group',
    description:
      'Lead sentence for a company, institution, band, or other organization.',
    defaultLang: 'en',
    fields: [
      {
        name: 'label',
        label: 'Organization label',
        type: 'text',
        required: true,
        placeholder: 'OpenAI',
      },
      {
        name: 'organization_type',
        label: 'Organization type',
        type: 'text',
        placeholder: 'artificial intelligence research company',
        helpText: 'Short NP describing what kind of organization this is.',
      },
      {
        name: 'sectors',
        label: 'Sector(s)',
        type: 'text',
        multivalue: true,
        placeholder: 'technology, artificial intelligence',
        helpText:
          'Comma-separated sector or industry labels (“banking”, “education”, …).',
      },
      {
        name: 'country',
        label: 'Country',
        type: 'text',
        placeholder: 'United States',
        helpText:
          'Country where the organization is headquartered or primarily based.',
      },
      {
        name: 'headquarters',
        label: 'Headquarters (city / region)',
        type: 'text',
        placeholder: 'San Francisco, California',
      },
      {
        name: 'founded_year',
        label: 'Founded (year)',
        type: 'number',
        placeholder: '2015',
      },
      {
        name: 'short_description',
        label: 'Short description',
        type: 'textarea',
        placeholder:
          'An American artificial intelligence research organization and company.',
      },
    ],
  },
  {
    slug: 'event-generic',
    frameType: 'event.generic',
    family: 'event',
    title: 'Generic event',
    description:
      'Temporally bounded event or episode: what happened, when, where, and to whom.',
    defaultLang: 'en',
    fields: [
      {
        name: 'label',
        label: 'Event label',
        type: 'text',
        required: true,
        placeholder: '2010 Chile earthquake',
      },
      {
        name: 'event_type',
        label: 'Event type',
        type: 'text',
        placeholder: 'earthquake, election, discovery',
        helpText:
          'Neutral type keyword used by the NLG layer to pick phrasing templates.',
      },
      {
        name: 'participants',
        label: 'Main participants',
        type: 'text',
        multivalue: true,
        placeholder: 'Government of Chile, Pacific coast cities',
        helpText:
          'Comma-separated labels for the main actors or participants in the event.',
      },
      {
        name: 'time',
        label: 'Time span',
        type: 'text',
        placeholder: '27 February 2010',
        helpText:
          'Coarse time description (date, year, or interval) for the event.',
      },
      {
        name: 'location',
        label: 'Location',
        type: 'text',
        placeholder: 'off the coast of central Chile',
      },
      {
        name: 'summary',
        label: 'Event summary',
        type: 'textarea',
        placeholder:
          'A magnitude 8.8 earthquake that struck off the coast, causing widespread damage and a tsunami.',
      },
    ],
  },
  {
    slug: 'rel-definition',
    frameType: 'rel.definition',
    family: 'rel',
    title: 'Definition / classification',
    description:
      'Reusable definitional fact: “X is a Y in domain Z”. Useful inside articles or as lead sentences.',
    defaultLang: 'en',
    fields: [
      {
        name: 'subject_label',
        label: 'Subject label',
        type: 'text',
        required: true,
        placeholder: 'Photosynthesis',
      },
      {
        name: 'definition',
        label: 'Definition phrase',
        type: 'textarea',
        required: true,
        placeholder: 'the process by which green plants and some other organisms convert light energy into chemical energy',
        helpText:
          'Neutral, single-sentence-style definition without trailing period.',
      },
      {
        name: 'domain',
        label: 'Domain / field',
        type: 'text',
        placeholder: 'biology, biochemistry',
        multivalue: true,
      },
      {
        name: 'sources',
        label: 'Source hints / notes',
        type: 'textarea',
        placeholder: 'Derived from Wikidata item Q123, property P279 and P31.',
        helpText:
          'Optional notes or provenance; may be echoed in meta frames or citations.',
      },
    ],
  },
  {
    slug: 'narr-timeline',
    frameType: 'narr.timeline',
    family: 'narr',
    title: 'Timeline / chronology',
    description:
      'Narrative frame for timelines: a sequence of dated events for a subject.',
    defaultLang: 'en',
    fields: [
      {
        name: 'subject_label',
        label: 'Subject label',
        type: 'text',
        required: true,
        placeholder: 'Career of Ada Lovelace',
      },
      {
        name: 'focus_period',
        label: 'Focus period',
        type: 'text',
        placeholder: '1815–1852',
        helpText:
          'Overall time range for the timeline (years or dates).',
      },
      {
        name: 'items',
        label: 'Timeline items',
        type: 'textarea',
        required: true,
        placeholder:
          '1833: Met Charles Babbage.\n1842–43: Translated and annotated Menabrea’s paper on the Analytical Engine.\n…',
        helpText:
          'One item per line, prefixed by a date or year. Upstream adapters can turn these into structured events.',
      },
    ],
  },
];

// Map from slug → context config for fast lookup.
export const FRAME_CONTEXTS_BY_SLUG: Record<string, FrameContextConfig> =
  FRAME_CONTEXTS.reduce<Record<string, FrameContextConfig>>((acc, ctx) => {
    acc[ctx.slug] = ctx;
    return acc;
  }, {});

// Convenience accessor with a simple fallback.
export function getFrameContext(slug: string): FrameContextConfig | undefined {
  return FRAME_CONTEXTS_BY_SLUG[slug];
}

// Default context used when none is specified.
export const DEFAULT_FRAME_CONTEXT: FrameContextConfig = FRAME_CONTEXTS[0];
