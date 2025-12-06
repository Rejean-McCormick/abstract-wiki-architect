// architect_frontend/src/app/abstract_wiki_architect/entities/[id]/page.tsx

import { notFound } from "next/navigation";
import EntityDetail from "@/components/EntityDetail";
import { getEntity } from "@/lib/entityApi";

type PageProps = {
  params: {
    id: string;
  };
};

/**
 * Entity detail page.
 *
 * Server component that fetches a single entity by ID and renders it
 * using the shared <EntityDetail> component.
 */
export default async function EntityPage({ params }: PageProps) {
  const { id } = params;

  if (!id) {
    notFound();
  }

  const entity = await getEntity(id);

  if (!entity) {
    notFound();
  }

  return (
    <div>
      <EntityDetail entity={entity} />
    </div>
  );
}
