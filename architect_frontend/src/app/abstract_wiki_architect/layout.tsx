// architect_frontend/src/app/abstract_wiki_architect/layout.tsx

import type { ReactNode } from "react";
import Link from "next/link";

import { FRAME_CONTEXTS } from "@/config/frameConfigs";

type Props = {
  children: ReactNode;
};

export default function AbstractWikiArchitectLayout({ children }: Props) {
  return (
    <main
      style={{
        display: "flex",
        minHeight: "100vh",
        fontFamily:
          'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      }}
    >
      <aside
        style={{
          width: "260px",
          padding: "1.5rem",
          borderRight: "1px solid #ddd",
          background: "#fafafa",
        }}
      >
        <header style={{ marginBottom: "1.5rem" }}>
          <h1
            style={{
              margin: 0,
              fontSize: "1.25rem",
            }}
          >
            Abstract Wiki Architect
          </h1>
          <p
            style={{
              margin: "0.5rem 0 0 0",
              fontSize: "0.85rem",
              color: "#555",
            }}
          >
            Frame-based, AI-assisted editor
          </p>
        </header>

        <nav>
          <h2
            style={{
              margin: "0 0 0.75rem 0",
              fontSize: "0.9rem",
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              color: "#777",
            }}
          >
            Contexts
          </h2>
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {FRAME_CONTEXTS.map((context) => (
              <li key={context.slug} style={{ marginBottom: "0.35rem" }}>
                <Link
                  href={`/abstract_wiki_architect/${context.slug}`}
                  style={{
                    display: "block",
                    padding: "0.3rem 0.2rem",
                    borderRadius: "4px",
                    textDecoration: "none",
                    fontSize: "0.95rem",
                  }}
                >
                  {context.title}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </aside>

      <section
        style={{
          flex: 1,
          padding: "2rem",
          minWidth: 0,
        }}
      >
        {children}
      </section>
    </main>
  );
}
