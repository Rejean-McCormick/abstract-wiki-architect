// architect_frontend/src/app/abstract_wiki_architect/page.tsx

import Link from "next/link";
import { frameConfigs } from "@/config/frameConfigs";

export default function AbstractWikiArchitectHomePage() {
  return (
    <main className="min-h-screen bg-slate-950 text-slate-50">
      <div className="mx-auto max-w-5xl px-4 py-10">
        <header className="mb-10 space-y-3">
          <p className="text-[11px] font-mono uppercase tracking-[0.25em] text-slate-400">
            Abstract Wiki Architect
          </p>
          <h1 className="text-3xl font-semibold tracking-tight">
            Choose a frame workspace
          </h1>
          <p className="max-w-3xl text-sm text-slate-300">
            Pick a semantic frame to open its generation workspace. Each frame
            has its own dedicated form, defaults, and language options. You can
            switch frames at any time from the workspace header.
          </p>
        </header>

        <section className="grid gap-4 md:grid-cols-2">
          {frameConfigs.map((frame) => (
            <Link
              key={frame.slug}
              href={`/abstract_wiki_architect/${frame.slug}`}
              className="group flex flex-col justify-between rounded-xl border border-slate-800 bg-slate-900/40 p-4 transition hover:border-sky-500 hover:bg-slate-900"
            >
              <div className="space-y-2">
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      {frame.icon && (
                        <span aria-hidden="true" className="text-lg">
                          {frame.icon}
                        </span>
                      )}
                      <h2 className="text-sm font-medium tracking-tight">
                        {frame.title}
                      </h2>
                    </div>
                    <p className="text-xs text-slate-300 line-clamp-3">
                      {frame.description}
                    </p>
                  </div>
                  <span className="text-[11px] font-medium uppercase tracking-[0.2em] text-slate-500 group-hover:text-sky-400">
                    Open
                  </span>
                </div>
              </div>

              <div className="mt-4 flex flex-wrap items-center gap-2">
                <span className="rounded-full bg-slate-800/80 px-2 py-0.5 text-[10px] font-mono uppercase tracking-wide text-slate-200">
                  {frame.frameType}
                </span>
                {frame.availableLangs && frame.availableLangs.length > 0 && (
                  <span className="rounded-full bg-slate-900/70 px-2 py-0.5 text-[10px] text-slate-400">
                    {frame.availableLangs.join(" · ")}
                  </span>
                )}
                {frame.tags &&
                  frame.tags.map((tag: string) => (
                    <span
                      key={tag}
                      className="rounded-full bg-slate-900/40 px-2 py-0.5 text-[10px] text-slate-400"
                    >
                      {tag}
                    </span>
                  ))}
              </div>
            </Link>
          ))}
        </section>
      </div>
    </main>
  );
}
