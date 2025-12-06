// architect_frontend/src/components/WorkspaceShell.tsx

import type { ReactNode } from "react";

export type FrameContextConfig = {
  // High-level grouping of the frame (e.g., "entity", "event", etc.)
  family: string;
  // Title shown in the workspace header
  title: string;
  // Optional description displayed under the title
  description?: string;
};

export type WorkspaceShellProps = {
  // Frame context this workspace is editing (bio, event, etc.)
  context: FrameContextConfig;

  // Main content area (typically the frame form + result).
  children: ReactNode;

  // Optional right-side panel (AI assistant, inspectors, extra details).
  rightPane?: ReactNode;

  // Optional footer content (actions, links).
  footer?: ReactNode;
};

/**
 * Generic workspace wrapper for a frame-based editing surface.
 *
 * Layout:
 *   - Header with title + description + family badge
 *   - Main area with two columns (left content, optional right pane)
 *   - Optional footer
 */
export default function WorkspaceShell({
  context,
  children,
  rightPane,
  footer,
}: WorkspaceShellProps) {
  const hasRightPane = Boolean(rightPane);

  return (
    <div className="awa-workspace">
      <header className="awa-workspace__header">
        <div className="awa-workspace__header-main">
          <span className="awa-workspace__family-badge">
            {context.family.toUpperCase()}
          </span>
          <h1 className="awa-workspace__title">{context.title}</h1>
        </div>
        {context.description && (
          <p className="awa-workspace__description">
            {context.description}
          </p>
        )}
      </header>

      <div
        className={
          hasRightPane
            ? "awa-workspace__body awa-workspace__body--two-column"
            : "awa-workspace__body awa-workspace__body--single-column"
        }
      >
        <section className="awa-workspace__main">{children}</section>
        {hasRightPane && (
          <aside className="awa-workspace__side">{rightPane}</aside>
        )}
      </div>

      {footer && <footer className="awa-workspace__footer">{footer}</footer>}
    </div>
  );
}
