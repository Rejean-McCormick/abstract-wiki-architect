// architect_frontend/src/__tests__/entities.test.tsx

import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Adjust import paths if your structure differs
import EntityList from "../components/EntityList";
import EntityDetail from "../components/EntityDetail";

type TestEntity = {
  id: string;
  label: string;
  type: string;
  description?: string;
};

const ENTITIES: TestEntity[] = [
  {
    id: "Q42",
    label: "Douglas Adams",
    type: "entity.person",
    description: "English writer and humorist.",
  },
  {
    id: "Q64",
    label: "Berlin",
    type: "entity.place.city",
    description: "Capital of Germany.",
  },
  {
    id: "Q328",
    label: "Wikipedia",
    type: "entity.creative_work",
    description: "Free online encyclopedia.",
  },
];

describe("EntityList", () => {
  test("renders all entities and highlights selected one", () => {
    const onSelect = jest.fn();

    render(
      <EntityList
        entities={ENTITIES}
        selectedId="Q64"
        onSelect={onSelect}
      />
    );

    // All labels are present
    for (const e of ENTITIES) {
      expect(screen.getByText(e.label)).toBeInTheDocument();
    }

    // Selected entity is marked (via aria-selected or a CSS hook)
    const selectedRow = screen.getByRole("option", { name: /Berlin/i });
    expect(selectedRow).toHaveAttribute("aria-selected", "true");
  });

  test("calls onSelect when an entity is clicked", async () => {
    const user = userEvent.setup();
    const onSelect = jest.fn();

    render(
      <EntityList
        entities={ENTITIES}
        selectedId={null}
        onSelect={onSelect}
      />
    );

    const target = screen.getByRole("option", { name: /Wikipedia/i });
    await user.click(target);

    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith("Q328");
  });

  test("renders an empty state when there are no entities", () => {
    const onSelect = jest.fn();

    render(
      <EntityList
        entities={[]}
        selectedId={null}
        onSelect={onSelect}
      />
    );

    expect(
      screen.getByText(/no entities found/i)
    ).toBeInTheDocument();
  });
});

describe("EntityDetail", () => {
  test("renders a loading indicator", () => {
    render(
      <EntityDetail
        entity={null}
        isLoading
        error={null}
      />
    );

    expect(
      screen.getByText(/loading entity/i)
    ).toBeInTheDocument();
  });

  test("renders an error message", () => {
    render(
      <EntityDetail
        entity={null}
        isLoading={false}
        error="Something went wrong"
      />
    );

    expect(
      screen.getByText(/something went wrong/i)
    ).toBeInTheDocument();
  });

  test("renders entity details when available", () => {
    const entity = ENTITIES[0];

    render(
      <EntityDetail
        entity={entity}
        isLoading={false}
        error={null}
      />
    );

    expect(
      screen.getByRole("heading", { name: entity.label })
    ).toBeInTheDocument();
    expect(
      screen.getByText(/english writer and humorist/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/entity\.person/i)
    ).toBeInTheDocument();
  });

  test("renders a placeholder when no entity is selected", () => {
    render(
      <EntityDetail
        entity={null}
        isLoading={false}
        error={null}
      />
    );

    expect(
      screen.getByText(/select an entity to inspect its frames/i)
    ).toBeInTheDocument();
  });
});
