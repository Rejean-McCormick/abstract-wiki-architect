// architect_frontend/src/app/tools/utils.ts

// Minimal shell-ish parser (whitespace split + quotes + backslash escapes).
// NOTE: This is intentionally simple; backend still validates/allowlists flags.
export function parseCliArgs(input: string): string[] {
  const out: string[] = [];
  let cur = "";
  let inSingle = false;
  let inDouble = false;

  const push = () => {
    if (cur.length) out.push(cur);
    cur = "";
  };

  for (let i = 0; i < input.length; i++) {
    const ch = input[i];

    // Backslash escapes next char (outside single quotes; inside double quotes it's common too)
    if (ch === "\\" && i + 1 < input.length) {
      // In single quotes, treat backslash literally (closer to shell behavior)
      if (inSingle) {
        cur += ch;
        continue;
      }
      cur += input[i + 1];
      i++;
      continue;
    }

    if (!inDouble && ch === "'") {
      inSingle = !inSingle;
      continue;
    }
    if (!inSingle && ch === '"') {
      inDouble = !inDouble;
      continue;
    }

    if (!inSingle && !inDouble && /\s/.test(ch)) {
      push();
      continue;
    }

    cur += ch;
  }
  push();
  return out;
}

/**
 * Best-effort clipboard helper.
 * Returns true if it likely succeeded, false otherwise.
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // fall through to legacy path
  }

  // Legacy fallback (works in more contexts, but not all)
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "true");
    ta.style.position = "fixed";
    ta.style.left = "-9999px";
    ta.style.top = "0";
    document.body.appendChild(ta);
    ta.select();
    ta.setSelectionRange(0, ta.value.length);
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    return ok;
  } catch {
    return false;
  }
}

export const docsHref = (key: string) => `#${key}`;

export const normalizeBaseUrl = (raw: string) => raw.replace(/\/$/, "");

export const normalizeApiV1 = (rawBase: string) => {
  const base = normalizeBaseUrl(rawBase);
  return base.endsWith("/api/v1") ? base : `${base}/api/v1`;
};

export const normalizeRepoUrl = (raw: string) => raw.replace(/\/$/, "");

// Keep "main" as default branch (consistent with current UI),
// but allow override via NEXT_PUBLIC_REPO_BRANCH.
export const repoFileUrl = (repoUrl: string, path: string) => {
  if (!repoUrl) return "";
  const branch = (process.env.NEXT_PUBLIC_REPO_BRANCH || "main").trim() || "main";
  return `${normalizeRepoUrl(repoUrl)}/blob/${branch}/${path}`;
};

/**
 * Utility: small, safe classnames combiner (no dependency).
 */
export function cx(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(" ");
}
