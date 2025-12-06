// architect_frontend/src/components/GenerationResult.tsx

import type { FC } from "react";
import type { GenericGenerateResponse } from "@/lib/api";

type GenerationResultProps = {
  result: GenericGenerateResponse | null;
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
      <p style={{ whiteSpace: "pre-wrap", lineHeight: 1.5 }}>{result.text}</p>
    </section>
  );
};

export default GenerationResult;
