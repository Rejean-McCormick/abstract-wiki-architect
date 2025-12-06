// architect_frontend/src/__tests__/api.test.ts

/**
 * Tests for the frontend API helper functions in src/lib/api.ts
 *
 * Assumptions:
 * - API functions are:
 *     - fetchFramesMetadata()
 *     - generateFrame(slug: string, payload: Record<string, unknown>)
 *     - getSuggestions(payload: { query: string; [key: string]: unknown })
 * - Each function uses global `fetch` and:
 *     - returns parsed JSON when `response.ok` is true
 *     - throws an Error when `response.ok` is false
 *
 * If your real `api.ts` differs slightly (names, arguments),
 * update the imports and expectations here to match.
 */

import {
  fetchFramesMetadata,
  generateFrame,
  getSuggestions,
} from '../lib/api';

type FetchMock = jest.MockedFunction<typeof fetch>;

const makeOkResponse = <T>(data: T, extra: Partial<Response> = {}): Response =>
  ({
    ok: true,
    status: 200,
    json: async () => data,
    text: async () => JSON.stringify(data),
    ...extra,
  } as unknown as Response);

const makeErrorResponse = (
  status: number,
  body: unknown = { detail: 'error' },
  extra: Partial<Response> = {},
): Response =>
  ({
    ok: false,
    status,
    json: async () => body,
    text: async () => JSON.stringify(body),
    ...extra,
  } as unknown as Response);

describe('frontend API helpers', () => {
  let originalFetch: typeof fetch;
  let fetchMock: FetchMock;

  beforeAll(() => {
    originalFetch = global.fetch;
  });

  beforeEach(() => {
    fetchMock = jest.fn() as FetchMock;
    (global as any).fetch = fetchMock;
  });

  afterEach(() => {
    jest.resetAllMocks();
    (global as any).fetch = originalFetch;
  });

  describe('fetchFramesMetadata', () => {
    it('calls the /frames endpoint and returns parsed JSON', async () => {
      const payload = [
        {
          slug: 'entity-person',
          title: 'Person',
          description: 'Entity: person',
          category: 'entity',
        },
      ];

      fetchMock.mockResolvedValueOnce(makeOkResponse(payload));

      const result = await fetchFramesMetadata();

      expect(fetchMock).toHaveBeenCalledTimes(1);
      const [url, options] = fetchMock.mock.calls[0];

      // We don’t assume exact base URL, only that it targets /frames
      expect(url.toString()).toContain('/frames');
      expect((options as RequestInit | undefined)?.method ?? 'GET').toBe('GET');

      expect(result).toEqual(payload);
    });

    it('throws a helpful error when the request fails', async () => {
      fetchMock.mockResolvedValueOnce(
        makeErrorResponse(500, { detail: 'Internal error' }),
      );

      await expect(fetchFramesMetadata()).rejects.toThrow(/frames/i);
      await expect(fetchFramesMetadata()).rejects.toBeInstanceOf(Error);
    });
  });

  describe('generateFrame', () => {
    const slug = 'entity-person';

    const requestBody = {
      frame_type: 'entity.person',
      inputs: {
        name: 'Marie Curie',
        language: 'en',
      },
    };

    const responseBody = {
      generation_id: 'gen_123',
      frame_type: 'entity.person',
      content: 'Marie Curie was a Polish-French physicist...',
      warnings: [],
    };

    it('POSTs JSON to a /generate endpoint including the frame slug', async () => {
      fetchMock.mockResolvedValueOnce(makeOkResponse(responseBody));

      const result = await generateFrame(slug, requestBody);

      expect(fetchMock).toHaveBeenCalledTimes(1);
      const [url, options] = fetchMock.mock.calls[0];

      expect(url.toString()).toContain('/generate');
      expect(url.toString()).toContain(slug);

      const opts = options as RequestInit;
      expect(opts.method).toBe('POST');
      expect(opts.headers).toMatchObject({
        'Content-Type': 'application/json',
      });

      const parsedBody = JSON.parse((opts.body as string) || '{}');
      expect(parsedBody).toEqual(requestBody);

      expect(result).toEqual(responseBody);
    });

    it('throws an error with status info when the backend returns !ok', async () => {
      fetchMock.mockResolvedValueOnce(
        makeErrorResponse(422, { detail: 'Validation error' }),
      );

      await expect(generateFrame(slug, requestBody)).rejects.toThrow(
        /generate/i,
      );
      await expect(generateFrame(slug, requestBody)).rejects.toThrow(/422/);
    });
  });

  describe('getSuggestions', () => {
    const suggestionRequest = {
      query: 'Marie Curie',
      frame_type: 'entity.person',
      max_suggestions: 3,
    };

    const suggestionResponse = {
      suggestions: [
        { label: 'Marie Skłodowska-Curie', id: 'Q7186' },
        { label: 'Maria Skłodowska', id: 'Q123456' },
      ],
    };

    it('POSTs to /ai/suggestions with the provided payload', async () => {
      fetchMock.mockResolvedValueOnce(makeOkResponse(suggestionResponse));

      const result = await getSuggestions(suggestionRequest);

      expect(fetchMock).toHaveBeenCalledTimes(1);
      const [url, options] = fetchMock.mock.calls[0];

      expect(url.toString()).toContain('/ai/suggestions');

      const opts = options as RequestInit;
      expect(opts.method).toBe('POST');
      expect(opts.headers).toMatchObject({
        'Content-Type': 'application/json',
      });

      const parsedBody = JSON.parse((opts.body as string) || '{}');
      expect(parsedBody).toEqual(suggestionRequest);

      expect(result).toEqual(suggestionResponse);
    });

    it('throws an error when suggestions endpoint fails', async () => {
      fetchMock.mockResolvedValueOnce(
        makeErrorResponse(400, { detail: 'Bad request' }),
      );

      await expect(getSuggestions(suggestionRequest)).rejects.toThrow(
        /suggest/i,
      );
      await expect(getSuggestions(suggestionRequest)).rejects.toThrow(/400/);
    });
  });
});
