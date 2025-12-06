// architect_frontend/src/components/ClientFrameWorkspace.tsx
"use client";

import React, { useState } from "react";
import FrameForm, { type FrameContextConfig } from "@/components/FrameForm";
import GenerationResult from "@/components/GenerationResult";
import ErrorBanner from "@/components/ErrorBanner";
import type { GenerationResult as GenerationResultType } from "@/lib/api";

type Props = {
  frameConfig: FrameContextConfig;
};

export default function ClientFrameWorkspace({ frameConfig }: Props) {
  const [result, setResult] = useState<GenerationResultType | null>(null);
  const [error, setError] = useState<string | null>(null);

  return (
    <>
      <ErrorBanner message={error} />

      <FrameForm
        frameConfig={frameConfig}
        onResult={(res) => {
          setResult(res);
          setError(null);
        }}
        onError={(msg) => {
          setError(msg instanceof Error ? msg.message : String(msg));
          setResult(null);
        }}
      />

      <GenerationResult result={result} />
    </>
  );
}