// architect_frontend/src/__tests__/entities.test.tsx

import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";

import EntityList from "../components/EntityList";
import EntityDetail from "../components/EntityDetail";
import { architectApi, type Entity } from "../lib/api";

// --- Setup Mocks for Next.js and API ---
// Note: You must ensure 'user-event' is installed: npm install @testing-library/user-event

// 1. Mock Next.js Router for navigation/redirection logic
const mockPush = jest.fn();
jest.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
  }),
  // Required to mock 'next/navigation' methods used in Server Components
  useSearchParams: () => ({
    get: jest.fn(),
  }),
  usePathname: () => "/",
}));

// 2. Mock the central API calls
jest.mock("../lib/api", () => {
  const actual = jest.requireActual("../lib/api");

  return {
    __esModule: true,
    ...actual,
    architectApi: {
      listEntities: jest.fn(),
      getEntity: jest.fn(),
      updateEntity: jest.fn(),
      deleteEntity: jest.fn(),
      // Include all other methods required by EntityDetail, e.g.,
      generate: jest.fn(),
      processIntent: jest.fn(),
    },
  };
});

// Helper to access the mock functions
const mockListEntities = architectApi.listEntities as jest.Mock;
const mockGetEntity = architectApi.getEntity as jest.Mock;
const mockUpdateEntity = architectApi.updateEntity as jest.Mock;

const MOCK_ENTITIES: Entity[] = [
  {
    id: 42,
    name: "Douglas Adams",
    frame_type: "entity.person",
    lang: "en",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    // Mapped from TestEntity props
    short_description: "English writer and humorist.",
  } as Entity,
  {
    id: 64,
    name: "Berlin",
    frame_type: "entity.place.city",
    lang: "de",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    short_description: "Capital of Germany.",
  } as Entity,
];

// --- EntityList Tests (Tests the actual data fetching component) ---

describe("EntityList (Smart Component)", () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  test("fetches and renders all entities on mount", async () => {
    mockListEntities.mockResolvedValueOnce(MOCK_ENTITIES);

    render(<EntityList />);

    // Renders loading state initially
    expect(screen.getByText(/Loading library/i)).toBeInTheDocument();

    // Wait for the API call to resolve and check the data
    await waitFor(() => expect(mockListEntities).toHaveBeenCalledTimes(1));

    expect(await screen.findByText("Douglas Adams")).toBeInTheDocument();
    expect(await screen.findByText("Berlin")).toBeInTheDocument();
    expect(screen.queryByText(/Loading library/i)).not.toBeInTheDocument();
  });

  test("navigates to entity detail on click", async () => {
    const user = userEvent.setup();
    mockListEntities.mockResolvedValueOnce(MOCK_ENTITIES);

    render(<EntityList />);

    await waitFor(() => expect(mockListEntities).toHaveBeenCalledTimes(1));

    const targetRow = screen.getByRole("row", { name: /Douglas Adams/i });
    await user.click(targetRow);

    // Should push to the detail page (as implemented in EntityList.tsx)
    expect(mockPush).toHaveBeenCalledWith(
      "/abstract_wiki_architect/entities/42",
    );
  });
});

// --- EntityDetail Tests (Tests the actual data fetching component) ---

describe("EntityDetail (Smart Component)", () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  test("fetches and renders details for the given ID", async () => {
    mockGetEntity.mockResolvedValueOnce(MOCK_ENTITIES[0]);

    // Passes only the required 'id' prop
    render(<EntityDetail id="42" />);

    // Renders loading state
    expect(
      screen.getByText(/Loading entity editor/i),
    ).toBeInTheDocument();

    // Wait for the API call to resolve
    await waitFor(() => expect(mockGetEntity).toHaveBeenCalledWith("42"));

    // Check if the key details from the fetched entity are rendered
    expect(
      await screen.findByRole("heading", { name: MOCK_ENTITIES[0].name }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/English writer and humorist/i),
    ).toBeInTheDocument();
  });

  test("allows saving and mocks the API update", async () => {
    const user = userEvent.setup();
    const updatedEntity = { ...MOCK_ENTITIES[0], name: "Douglas Adams II" };

    // Setup initial fetch and update mock
    mockGetEntity.mockResolvedValueOnce(MOCK_ENTITIES[0]);
    mockUpdateEntity.mockResolvedValueOnce(updatedEntity);

    render(<EntityDetail id="42" />);
    await waitFor(() => expect(mockGetEntity).toHaveBeenCalled());

    // Locate the JSON editor (mock user typing a change)
    const jsonEditor = screen.getByRole("textbox", { name: /Frame Payload/i });
    fireEvent.change(jsonEditor, {
      target: { value: '{"name": "Douglas Adams II"}' },
    });

    // Click save
    const saveButton = screen.getByRole("button", {
      name: /Save Changes/i,
    });
    await user.click(saveButton);

    // Wait for the update call
    await waitFor(() => expect(mockUpdateEntity).toHaveBeenCalledTimes(1));

    // Verify the update payload
    expect(mockUpdateEntity).toHaveBeenCalledWith("42", {
      frame_payload: { name: "Douglas Adams II" },
    });

    // Verify the UI updates with the new entity data after the save resolves
    expect(
      await screen.findByRole("heading", { name: /Douglas Adams II/i }),
    ).toBeInTheDocument();
  });

  test("renders an error on fetch failure", async () => {
    mockGetEntity.mockRejectedValueOnce(new Error("Network Error"));

    render(<EntityDetail id="999" />);

    await waitFor(() => expect(mockGetEntity).toHaveBeenCalled());

    expect(
      screen.getByText(
        /Could not load entity\. It may not exist or the backend is down\./i,
      ),
    ).toBeInTheDocument();
  });
});
