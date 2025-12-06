// architect_frontend/src/__tests__/aiPanel.test.tsx

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";

import AIPanel from "../components/AIPanel";
import { architectApi } from "../lib/api";

// Mock the API module to intercept calls
jest.mock("../lib/api", () => ({
  architectApi: {
    processIntent: jest.fn(),
  },
}));

// Helper to access the mock function with proper typing
const mockProcessIntent = architectApi.processIntent as jest.Mock;

const baseProps = {
  entityType: "bio",
  entityId: "person",
  currentValues: { name: "Marie Curie" },
  onApplySuggestion: jest.fn(),
};

describe("AIPanel", () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  it("renders basic AI controls", () => {
    render(<AIPanel {...baseProps} />);

    expect(screen.getByText(/Architect AI/i)).toBeInTheDocument();
    
    // Check for the "Suggest" button (mapped to 'suggest_missing' preset)
    expect(screen.getByRole("button", { name: /Suggest/i })).toBeInTheDocument();
    
    // Check for "Explain" button
    expect(screen.getByRole("button", { name: /Explain/i })).toBeInTheDocument();
    
    // Check input placeholder
    expect(screen.getByPlaceholderText(/Type your instructions/i)).toBeInTheDocument();
  });

  it("sends a request and handles suggestions", async () => {
    // 1. Mock a successful response from the backend with a patch
    mockProcessIntent.mockResolvedValueOnce({
      intent_label: "suggest_fields",
      assistant_messages: [
        { role: "assistant", content: "I suggest setting the profession." }
      ],
      patches: [
        { path: "profession", value: "physicist", op: "add" }
      ]
    });

    const onApplySuggestion = jest.fn();
    render(
      <AIPanel
        {...baseProps}
        onApplySuggestion={onApplySuggestion}
      />
    );

    // 2. Click "Suggest" button to trigger the 'suggest_missing' preset
    fireEvent.click(screen.getByRole("button", { name: /Suggest/i }));

    // 3. Wait for API call to complete
    await waitFor(() =>
      expect(mockProcessIntent).toHaveBeenCalledTimes(1)
    );

    // 4. Verify request payload matches the new API structure
    expect(mockProcessIntent).toHaveBeenCalledWith(expect.objectContaining({
      message: expect.stringContaining("missing or underspecified"), // The preset text
      context_frame: {
        frame_type: "bio",
        payload: { name: "Marie Curie" }
      }
    }));

    // 5. Verify response handling: 
    // The assistant's message should appear in the chat
    expect(await screen.findByText(/I suggest setting the profession/i)).toBeInTheDocument();

    // The "Suggestion Available" banner should appear because we returned patches
    expect(screen.getByText(/Suggestion Available/i)).toBeInTheDocument();

    // 6. Click "Apply Changes"
    fireEvent.click(screen.getByRole("button", { name: /Apply Changes/i }));

    // 7. Verify the callback was fired with the correct data
    expect(onApplySuggestion).toHaveBeenCalledWith({
      profession: "physicist"
    });
  });
});