// architect_frontend/src/components/GenerationResult.tsx

import type { FC } from "react";
import type { GenerationResult as GenerationResultData } from "@/lib/api";

type GenerationResultProps = {
  result: GenerationResultData | null;
  title?: string;
  className?: string;
};

const GenerationResult: FC<GenerationResultProps> = ({
  result,
  title = "Generated text",
  className,
}) => {
  if (!result) return null;

  return (
    <section
      className={className}
      style={{
        marginTop: "1.5rem",
        padding: "1rem",
        background: "#fff",
        borderRadius: "4px",
        boxShadow: "0 0 0 1px #ddd",
        maxWidth: "640px",
      }}
    >
      <h2 style={{ marginTop: 0 }}>{title}</h2>
      {/* Updated to match the 'surface_text' field from the new API response structure */}
      <p style={{ whiteSpace: "pre-wrap", lineHeight: 1.5 }}>
        {result.surface_text}
      </p>
    </section>
  );
};

export default GenerationResult;