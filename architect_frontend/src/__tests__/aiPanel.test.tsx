// architect_frontend/src/__tests__/aiPanel.test.tsx

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";

import AIPanel from "../components/AIPanel";
import * as aiApi from "../lib/aiApi";

const mockRequestAISuggestions = jest.spyOn(aiApi, "requestAISuggestions");
const mockRequestAIExplanation = jest.spyOn(aiApi, "requestAIExplanation");

const baseProps = {
  frameType: "bio",
  frameSlug: "person",
  currentValues: { name: "Marie Curie" },
  onApplySuggestion: jest.fn(),
};

describe("AIPanel", () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  it("renders basic AI controls", () => {
    render(<AIPanel {...baseProps} />);

    expect(screen.getByText(/AI assistant/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /suggest fields/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /ask ai/i })
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText(/ask ai about this frame/i)
    ).toBeInTheDocument();
  });

  it("requests suggestions and renders them, allowing apply", async () => {
    const suggestions = [
      {
        field: "profession",
        value: "physicist",
        reason: "Based on known data about Marie Curie.",
      },
    ];

    mockRequestAISuggestions.mockResolvedValueOnce(suggestions);

    const onApplySuggestion = jest.fn();
    render(
      <AIPanel
        {...baseProps}
        onApplySuggestion={onApplySuggestion}
      />
    );

    fireEvent.click(
      screen.getByRole("button", { name: /suggest fields/i })
    );

    await waitFor(() =>
      expect(mockRequestAISuggestions).toHaveBeenCalledTimes(1)
    );

    expect(mockRequestAISuggestions).toHaveBeenCalledWith({
      frameType: "bio",
      frameSlug: "person",
      values: { name: "Marie Curie" },
    });

    // Suggestion list should show the suggested field/value
    expect(screen.getByText(/profession/i)).toBeInTheDocument();
    expect(screen.getByText(/physicist/i)).toBeInTheDocument();

    const applyButtons = screen.getAllByRole("button", {
      name: /apply suggestion/i,
    });
    fireEvent.click(applyButtons[0]);

    expect(onApplySuggestion).toHaveBeenCalledTimes(1);
    expect(onApplySuggestion).toHaveBeenCalledWith({
      profession: "physicist",
    });
  });

  it("sends a question to the AI and renders the explanation", async () => {
    const explanation =
      "The biography focuses on Curie's pioneering work in radioactivity.";

    mockRequestAIExplanation.mockResolvedValueOnce(explanation);

    render(<AIPanel {...baseProps} />);

    const questionInput = screen.getByPlaceholderText(
      /ask ai about this frame/i
    );
    fireEvent.change(questionInput, {
      target: { value: "Why is her work considered pioneering?" },
    });

    fireEvent.click(screen.getByRole("button", { name: /ask ai/i }));

    await waitFor(() =>
      expect(mockRequestAIExplanation).toHaveBeenCalledTimes(1)
    );

    expect(mockRequestAIExplanation).toHaveBeenCalledWith({
      frameType: "bio",
      frameSlug: "person",
      values: { name: "Marie Curie" },
      question: "Why is her work considered pioneering?",
    });

    await waitFor(() =>
      expect(
        screen.getByText(
          /The biography focuses on Curie's pioneering work in radioactivity./i
        )
      ).toBeInTheDocument()
    );
  });

  it("shows a loading indicator while waiting for AI", async () => {
    let resolveSuggestions: ((value: any) => void) | null = null;

    mockRequestAISuggestions.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveSuggestions = resolve;
        })
    );

    render(<AIPanel {...baseProps} />);

    fireEvent.click(
      screen.getByRole("button", { name: /suggest fields/i })
    );

    // While the promise is pending, a loading indicator should appear
    expect(screen.getByText(/thinking/i)).toBeInTheDocument();

    // Resolve the promise to finish the request
    resolveSuggestions &&
      resolveSuggestions([
        { field: "profession", value: "physicist", reason: "test" },
      ]);

    await waitFor(() =>
      expect(screen.queryByText(/thinking/i)).not.toBeInTheDocument()
    );
  });
});
