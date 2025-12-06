// architect_frontend/src/app/page.tsx

import { redirect } from "next/navigation";

/**
 * Root route for the frontend.
 *
 * We treat `/abstract_wiki_architect` as the main workspace,
 * so the app root simply redirects there.
 */
export default function RootPage() {
  redirect("/abstract_wiki_architect");
}
