// architect_frontend/src/app/abstract_wiki_architect/entities/[id]/page.tsx

import React from "react";
import EntityDetail from "@/components/EntityDetail";

type PageProps = {
  params: {
    id: string;
  };
};

/**
 * Entity detail page.
 *
 * This Server Component acts as a wrapper. It extracts the `id` from the route
 * and renders the client-side <EntityDetail> editor.
 * * Data fetching is now handled inside EntityDetail via architectApi
 * to support the dynamic editor/AI workflows.
 */
export default function EntityPage({ params }: PageProps) {
  // In Next.js App Router, params are accessible here.
  const { id } = params;

  return (
    <div className="min-h-screen bg-slate-50 p-4 md:p-6">
      <EntityDetail id={id} />
    </div>
  );
}