// architect_frontend/src/app/abstract_wiki_architect/[slug]/page.tsx
"use client";

import { useState } from "react";
import { notFound } from "next/navigation";

import FrameForm from "@/components/FrameForm";
import GenerationResult from "@/components/GenerationResult";
import ErrorBanner from "@/components/ErrorBanner";

import { getFrameContextBySlug } from "@/config/frameConfigs";
import type { GenericGenerateResponse } from "@/lib/api";

type PageProps = {
  params: {
    slug: string;
  };
};

export default function FramePage({ params }: PageProps) {
  const context = getFrameContextBySlug(params.slug);
  const [result, setResult] = useState<GenericGenerateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!context) {
    notFound();
  }

  return (
    <div>
      <header style={{ marginBottom: "1.5rem" }}>
        <h1 style={{ margin: 0 }}>{context.title}</h1>
        {context.description && (
          <p style={{ marginTop: "0.5rem", maxWidth: "48rem" }}>
            {context.description}
          </p>
        )}
      </header>

      <ErrorBanner message={error} />

      <FrameForm
        context={context}
        onResult={(res) => {
          setResult(res);
          setError(null);
        }}
        onError={(msg) => {
          setError(msg);
          if (msg) {
            setResult(null);
          }
        }}
      />

      <GenerationResult result={result} />
    </div>
  );
}
