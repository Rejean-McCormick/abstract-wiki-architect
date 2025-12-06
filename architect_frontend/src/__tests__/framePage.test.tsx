// architect_frontend/src/__tests__/framePage.test.tsx

import "@testing-library/jest-dom";
import { render, screen, fireEvent } from "@testing-library/react";

import FramePage from "@/app/abstract_wiki_architect/[slug]/page";

// Mock the FrameForm so we can drive the page state without depending on
// actual form details.
jest.mock("@/components/FrameForm", () => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return function MockFrameForm(props: any) {
    return (
      <div>
        <div data-testid="frame-form-mock" />
        <button
          type="button"
          onClick={() =>
            props.onResult?.({
              text: "Generated biography text",
            })
          }
        >
          Trigger result
        </button>
        <button
          type="button"
          onClick={() => props.onError?.("Something went wrong")}
        >
          Trigger error
        </button>
      </div>
    );
  };
});

describe("FramePage", () => {
  it("renders the correct title and description for the bio context", () => {
    render(<FramePage params={{ slug: "bio" }} />);

    // Title comes from FRAME_CONTEXTS (bio context).
    expect(
      screen.getByRole("heading", { name: /person biography/i }),
    ).toBeInTheDocument();

    // Description text should also be visible.
    expect(
      screen.getByText(/lead sentence for a person/i),
    ).toBeInTheDocument();
  });

  it("shows the generation result after FrameForm triggers onResult", () => {
    render(<FramePage params={{ slug: "bio" }} />);

    fireEvent.click(screen.getByText(/trigger result/i));

    expect(
      screen.getByText("Generated biography text"),
    ).toBeInTheDocument();
  });

  it("shows an error when FrameForm triggers onError", () => {
    render(<FramePage params={{ slug: "bio" }} />);

    fireEvent.click(screen.getByText(/trigger error/i));

    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
  });
});
