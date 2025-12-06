// architect_frontend/src/app/abstract_wiki_architect/[slug]/page.tsx

import { notFound } from "next/navigation";
import { architectApi } from "@/lib/api";
import { adaptFrameConfig } from "@/lib/frameAdapter";
import ClientFrameWorkspace from "@/components/ClientFrameWorkspace";

type PageProps = {
  params: {
    slug: string;
  };
};

export default async function FramePage({ params }: PageProps) {
  const { slug } = params;

  try {
    // 1. Fetch Metadata (for title/description) and Schema (for fields) in parallel
    const [metaList, schema] = await Promise.all([
      architectApi.listFrameTypes(),
      architectApi.getFrameSchema(slug),
    ]);

    // 2. Find the metadata for this specific frame type
    const meta = metaList.find((m) => m.frame_type === slug);

    if (!meta || !schema) {
      notFound();
    }

    // 3. Adapt Backend Schema -> Frontend Config
    const frameConfig = adaptFrameConfig(meta, schema);

    return (
      <div>
        {/* Static Header Rendered on Server */}
        <header style={{ marginBottom: "1.5rem" }}>
          <h1 style={{ margin: 0 }}>{frameConfig.label}</h1>
          {frameConfig.description && (
            <p style={{ marginTop: "0.5rem", maxWidth: "48rem" }}>
              {frameConfig.description}
            </p>
          )}
        </header>

        {/* Interactive Workspace (Form + Results) */}
        <ClientFrameWorkspace frameConfig={frameConfig} />
      </div>
    );
  } catch (error) {
    console.error("Error loading frame context", error);
    notFound();
  }
}