// architect_frontend/src/app/tools/__tests__/workflowFilter.test.tsx

import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";

import ToolsDashboard from "../page";
import { buildToolItems } from "../lib/buildToolItems";
import { useToolRunner } from "../hooks/useToolRunner";

jest.mock("../inventory", () => ({
  INVENTORY: {
    version: "test",
    generated_on: "2026-03-07",
  },
}));

jest.mock("../lib/buildToolItems", () => ({
  buildToolItems: jest.fn(),
}));

jest.mock("../hooks/useToolRunner", () => ({
  useToolRunner: jest.fn(),
}));

jest.mock("../components/ToolListPanel", () => {
  const React = require("react");

  function flattenGrouped(grouped: Map<string, Map<string, any[]>>) {
    const out: any[] = [];
    grouped.forEach((byGroup) => {
      byGroup.forEach((arr) => out.push(...arr));
    });
    return out;
  }

  return {
    __esModule: true,
    default: function ToolListPanelMock({
      grouped,
      selectedKey,
      onSelect,
      onRun,
    }: {
      grouped: Map<string, Map<string, any[]>>;
      selectedKey: string | null;
      onSelect: (key: string) => void;
      onRun: (it: any) => void;
    }) {
      const items = flattenGrouped(grouped);
      return (
        <div data-testid="tool-list">
          {items.map((it) => (
            <div key={it.key} data-testid={`tool-${it.key}`}>
              <button type="button" onClick={() => onSelect(it.key)}>
                {it.title}
              </button>
              <button
                type="button"
                onClick={() => onRun(it)}
                aria-label={`run-${it.title}`}
              >
                Run
              </button>
              {selectedKey === it.key ? <span data-testid="selected-tool">selected</span> : null}
            </div>
          ))}
        </div>
      );
    },
  };
});

jest.mock("../components/ToolDetailsCard", () => {
  const React = require("react");
  return {
    __esModule: true,
    default: function ToolDetailsCardMock({ selected }: { selected: any }) {
      return (
        <div data-testid="tool-details">
          {selected ? `selected:${selected.title}` : "selected:none"}
        </div>
      );
    },
  };
});

jest.mock("../components/ConsoleCard", () => {
  const React = require("react");
  return {
    __esModule: true,
    default: function ConsoleCardMock() {
      return <div data-testid="console-card">console</div>;
    },
  };
});

type MockToolItem = {
  key: string;
  title: string;
  path: string;
  category: string;
  group: string;
  toolIdGuess: string;
  wiredToolId?: string | null;
  kind: string;
  status: string;
  risk: string;
  hiddenInNormalMode?: boolean;
};

const mockBuildToolItems = buildToolItems as jest.MockedFunction<typeof buildToolItems>;
const mockUseToolRunner = useToolRunner as jest.MockedFunction<typeof useToolRunner>;

function tool(overrides: Partial<MockToolItem>): MockToolItem {
  const id = overrides.wiredToolId ?? overrides.toolIdGuess ?? overrides.key ?? "tool";
  return {
    key: overrides.key ?? String(id),
    title: overrides.title ?? String(id),
    path: overrides.path ?? `tools/${id}.py`,
    category: overrides.category ?? "Tools",
    group: overrides.group ?? "General",
    toolIdGuess: overrides.toolIdGuess ?? String(id),
    wiredToolId: overrides.wiredToolId ?? String(id),
    kind: overrides.kind ?? "tool",
    status: overrides.status ?? "active",
    risk: overrides.risk ?? "safe",
    hiddenInNormalMode: overrides.hiddenInNormalMode ?? false,
  };
}

const MOCK_ITEMS: MockToolItem[] = [
  tool({
    key: "build_index",
    title: "Build Index",
    wiredToolId: "build_index",
    category: "Build",
    group: "Matrix",
  }),
  tool({
    key: "compile_pgf",
    title: "Compile PGF",
    wiredToolId: "compile_pgf",
    category: "Build",
    group: "Compiler",
  }),
  tool({
    key: "language_health",
    title: "Language Health",
    wiredToolId: "language_health",
    category: "Validation",
    group: "Health",
  }),
  tool({
    key: "run_judge",
    title: "Run Judge",
    wiredToolId: "run_judge",
    category: "QA",
    group: "Judge",
  }),
  tool({
    key: "lexicon_coverage",
    title: "Lexicon Coverage Report",
    wiredToolId: "lexicon_coverage",
    category: "Lexicon",
    group: "Coverage",
  }),
  tool({
    key: "gap_filler",
    title: "Gap Filler",
    wiredToolId: "gap_filler",
    category: "Lexicon",
    group: "Assist",
  }),
  tool({
    key: "harvest_lexicon",
    title: "Harvest Lexicon",
    wiredToolId: "harvest_lexicon",
    category: "Lexicon",
    group: "Assist",
  }),
  tool({
    key: "bootstrap_tier1",
    title: "Bootstrap Tier 1",
    wiredToolId: "bootstrap_tier1",
    category: "Build",
    group: "Bootstrap",
    hiddenInNormalMode: true,
  }),
  tool({
    key: "diagnostic_audit",
    title: "Diagnostic Audit",
    wiredToolId: "diagnostic_audit",
    category: "Debug",
    group: "Recovery",
  }),
  tool({
    key: "profiler",
    title: "Profiler",
    wiredToolId: "profiler",
    category: "QA",
    group: "Performance",
  }),
  tool({
    key: "ai_refiner",
    title: "AI Refiner",
    wiredToolId: "ai_refiner",
    category: "AI",
    group: "Assist",
    hiddenInNormalMode: true,
  }),
  tool({
    key: "seed_lexicon",
    title: "Seed Lexicon",
    wiredToolId: "seed_lexicon",
    category: "AI",
    group: "Assist",
    hiddenInNormalMode: true,
  }),
  tool({
    key: "test_api_smoke",
    title: "API Smoke Test",
    wiredToolId: "test_api_smoke",
    category: "QA",
    group: "Pytest",
    kind: "test",
  }),
  tool({
    key: "legacy_tool",
    title: "Legacy Tool",
    wiredToolId: "legacy_tool",
    category: "Legacy",
    group: "Old",
    status: "legacy",
  }),
  tool({
    key: "internal_tool",
    title: "Internal Tool",
    wiredToolId: "internal_tool",
    category: "Internal",
    group: "Private",
    status: "internal",
  }),
  tool({
    key: "not_wired",
    title: "Not Wired",
    wiredToolId: null,
    category: "Misc",
    group: "Misc",
  }),
];

function setup() {
  render(<ToolsDashboard />);
}

describe("workflowFilter", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    window.localStorage.clear();

    mockBuildToolItems.mockReturnValue(MOCK_ITEMS as any);

    mockUseToolRunner.mockReturnValue({
      consoleOutput: "",
      appendConsole: jest.fn(),
      clear: jest.fn(),
      cancelRun: jest.fn(),
      runTool: jest.fn().mockResolvedValue({ ok: true }),
      activeToolId: null,
      lastStatus: null,
      lastResponseJson: null,
      visualData: null,
      setVisualData: jest.fn(),
    } as any);

    global.fetch = jest.fn().mockResolvedValue({
      text: async () =>
        JSON.stringify({
          broker: "ok",
          storage: "ok",
          engine: "ok",
        }),
    }) as jest.Mock;
  });

  it("shows the recommended workflow by default and filters to the recommended tool set", async () => {
    setup();

    expect(screen.getByText("Recommended workflow")).toBeInTheDocument();
    expect(screen.getByText("Shortest safe path for most normal work.")).toBeInTheDocument();

    expect(screen.getByText("Build Index")).toBeInTheDocument();
    expect(screen.getByText("Compile PGF")).toBeInTheDocument();
    expect(screen.getByText("Language Health")).toBeInTheDocument();
    expect(screen.getByText("Run Judge")).toBeInTheDocument();

    expect(screen.queryByText("Lexicon Coverage Report")).not.toBeInTheDocument();
    expect(screen.queryByText("Bootstrap Tier 1")).not.toBeInTheDocument();
    expect(screen.queryByText("AI Refiner")).not.toBeInTheDocument();

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/health/ready",
        expect.objectContaining({ cache: "no-store" })
      );
    });
  });

  it("switches to the language integration workflow and updates both card and visible tools", async () => {
    const user = userEvent.setup();
    setup();

    await user.selectOptions(
      screen.getByRole("combobox"),
      "language_integration"
    );

    expect(screen.getByText("Language integration workflow")).toBeInTheDocument();
    expect(
      screen.getByText("Use this when adding or repairing one language.")
    ).toBeInTheDocument();

    expect(screen.getByText("Lexicon Coverage Report")).toBeInTheDocument();
    expect(screen.getByText("Gap Filler")).toBeInTheDocument();
    expect(screen.getByText("Harvest Lexicon")).toBeInTheDocument();

    expect(screen.queryByText("Diagnostic Audit")).not.toBeInTheDocument();
    expect(screen.queryByText("API Smoke Test")).not.toBeInTheDocument();
    expect(screen.queryByText("AI Refiner")).not.toBeInTheDocument();
  });

  it("reveals hidden workflow tools when power user mode is enabled", async () => {
    const user = userEvent.setup();
    setup();

    await user.selectOptions(
      screen.getByRole("combobox"),
      "language_integration"
    );

    expect(screen.queryByText("Bootstrap Tier 1")).not.toBeInTheDocument();

    await user.click(screen.getByLabelText("Power user (debug)"));

    expect(screen.getByText("Bootstrap Tier 1")).toBeInTheDocument();
  });

  it("shows AI assist tools only when the AI workflow is selected and power user is enabled", async () => {
    const user = userEvent.setup();
    setup();

    await user.selectOptions(screen.getByRole("combobox"), "ai_assist");

    expect(screen.getByText("AI Assist workflow")).toBeInTheDocument();
    expect(screen.queryByText("AI Refiner")).not.toBeInTheDocument();
    expect(screen.queryByText("Seed Lexicon")).not.toBeInTheDocument();

    await user.click(screen.getByLabelText("Power user (debug)"));

    expect(screen.getByText("AI Refiner")).toBeInTheDocument();
    expect(screen.getByText("Seed Lexicon")).toBeInTheDocument();
  });

  it("persists the selected workflow filter in localStorage", async () => {
    const user = userEvent.setup();
    setup();

    await user.selectOptions(screen.getByRole("combobox"), "qa_validation");

    const raw = window.localStorage.getItem("tools_dashboard_prefs_v4");
    expect(raw).toBeTruthy();

    const parsed = JSON.parse(raw as string);
    expect(parsed.workflowFilter).toBe("qa_validation");
  });
});
