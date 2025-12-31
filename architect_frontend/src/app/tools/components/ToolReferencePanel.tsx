// architect_frontend/src/app/tools/components/ToolReferencePanel.tsx
"use client";

import React from "react";
import Link from "next/link";
import { ExternalLink, Copy, Info, Play } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

import { RiskBadge, StatusBadge, WiringBadge } from "./Badges";
import type { ToolItem } from "../types";
import { copyToClipboard, docsHref, repoFileUrl } from "../utils";
import { iconForCategory } from "./icons";

export function ToolReferencePanel(props: {
  enabled: boolean; // show only when power-user is enabled
  grouped: Map<string, Map<string, ToolItem[]>>;
  repoUrl: string;
  activeToolId: string | null;
  argsByToolId: Record<string, string>;
  setArgsByToolId: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  runTool: (it: ToolItem) => void;
}) {
  const { enabled, grouped, repoUrl, activeToolId, argsByToolId, setArgsByToolId, runTool } = props;

  if (!enabled) return null;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2">
          <Info className="w-4 h-4 text-slate-500" />
          Reference (click to expand)
        </CardTitle>
      </CardHeader>

      <CardContent className="space-y-3">
        <p className="text-sm text-slate-600">
          Every item below is linkable via its anchor. Use the left menu “Docs” button.
        </p>

        {[...grouped.entries()]
          .sort((a, b) => a[0].localeCompare(b[0]))
          .map(([cat, byGroup]) => (
            <div key={cat} className="space-y-2">
              <div className="flex items-center gap-2">
                {iconForCategory(cat)}
                <h3 className="font-semibold text-slate-800">{cat}</h3>
              </div>

              {[...byGroup.entries()]
                .sort((a, b) => a[0].localeCompare(b[0]))
                .map(([groupName, groupItems]) => (
                  <div key={groupName} className="space-y-2 pl-2">
                    <div className="text-xs font-semibold text-slate-500">{groupName}</div>

                    <div className="space-y-2">
                      {groupItems.map((it) => (
                        <details key={it.key} id={it.key} className="rounded-lg border border-slate-200 bg-white">
                          <summary className="cursor-pointer select-none list-none px-4 py-3 flex items-center justify-between gap-3">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="font-semibold text-sm text-slate-800">{it.title}</span>
                              <WiringBadge wired={Boolean(it.wiredToolId)} hidden={Boolean(it.hidden)} />
                              <RiskBadge risk={it.risk} />
                              <StatusBadge status={it.status} />
                              <span className="font-mono text-[11px] text-slate-500">{it.path}</span>
                            </div>
                            <span className="text-xs text-slate-500">Expand</span>
                          </summary>

                          <div className="px-4 pb-4 pt-1 text-sm text-slate-700 space-y-3">
                            {it.desc ? <div className="text-slate-600">{it.desc}</div> : null}

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                              {/* Run / wiring */}
                              <div className="rounded-md border border-slate-200 p-3 bg-slate-50">
                                <div className="text-xs text-slate-500 mb-1">tool_id</div>

                                <div className="font-mono text-xs flex items-center justify-between gap-2">
                                  <span>{it.wiredToolId ?? "—"}</span>
                                  <button
                                    className="text-slate-500 hover:text-slate-800 disabled:opacity-50"
                                    onClick={() => it.wiredToolId && copyToClipboard(it.wiredToolId)}
                                    disabled={!it.wiredToolId}
                                    title="Copy tool_id"
                                    aria-label="Copy tool_id"
                                  >
                                    <Copy className="w-3 h-3" />
                                  </button>
                                </div>

                                <div className="mt-2 flex gap-2 flex-wrap">
                                  <Button
                                    size="sm"
                                    onClick={() => runTool(it)}
                                    disabled={activeToolId !== null || !it.wiredToolId}
                                    variant={it.risk === "heavy" ? "destructive" : "default"}
                                    title={it.wiredToolId ? "Run (backend-wired)" : "Run disabled (not wired)"}
                                  >
                                    <Play className="w-4 h-4 mr-1" /> Run
                                  </Button>

                                  <Button variant="outline" size="sm" onClick={() => copyToClipboard(it.path)}>
                                    <Copy className="w-4 h-4 mr-1" /> Copy path
                                  </Button>

                                  {repoFileUrl(repoUrl, it.path) ? (
                                    <a
                                      href={repoFileUrl(repoUrl, it.path)}
                                      target="_blank"
                                      rel="noreferrer"
                                      className="inline-flex items-center gap-1 text-xs rounded-md border border-slate-200 px-2 py-1 text-slate-600 hover:bg-slate-50"
                                    >
                                      Open in Repo <ExternalLink className="w-3 h-3" />
                                    </a>
                                  ) : null}
                                </div>

                                {it.wiredToolId ? (
                                  <div className="mt-3">
                                    <div className="text-xs text-slate-500 mb-1">Args</div>
                                    <input
                                      value={argsByToolId[it.wiredToolId] || ""}
                                      onChange={(e) =>
                                        setArgsByToolId((prev) => ({
                                          ...prev,
                                          [it.wiredToolId as string]: e.target.value,
                                        }))
                                      }
                                      placeholder='e.g. --lang fr --dry-run'
                                      className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm font-mono outline-none focus:ring-2 focus:ring-blue-200"
                                      disabled={activeToolId !== null}
                                    />
                                    {it.commandPreview ? (
                                      <div className="mt-2 text-[11px] text-slate-500">
                                        Command preview: <span className="font-mono">{it.commandPreview}</span>
                                      </div>
                                    ) : null}
                                  </div>
                                ) : (
                                  <div className="mt-3 text-[11px] text-slate-500">
                                    tool_id guess: <span className="font-mono">{it.toolIdGuess}</span>
                                  </div>
                                )}
                              </div>

                              {/* CLI */}
                              <div className="rounded-md border border-slate-200 p-3 bg-slate-50">
                                <div className="text-xs text-slate-500 mb-1">CLI</div>
                                <div className="space-y-1">
                                  {it.cli.map((cmd) => (
                                    <div key={cmd} className="font-mono text-xs flex items-center justify-between gap-2">
                                      <span className="truncate">{cmd}</span>
                                      <button
                                        className="text-slate-500 hover:text-slate-800"
                                        onClick={() => copyToClipboard(cmd)}
                                        title="Copy command"
                                        aria-label="Copy command"
                                      >
                                        <Copy className="w-3 h-3" />
                                      </button>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            </div>

                            {/* Steps + Notes */}
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                              <div className="rounded-md border border-slate-200 p-3">
                                <div className="text-xs text-slate-500 mb-2">Interface steps</div>
                                <div className="space-y-1">
                                  {it.uiSteps.map((n) => (
                                    <div key={n} className="text-xs text-slate-700">
                                      • {n}
                                    </div>
                                  ))}
                                </div>
                              </div>

                              <div className="rounded-md border border-slate-200 p-3">
                                <div className="text-xs text-slate-500 mb-2">Notes</div>
                                <div className="space-y-1">
                                  {it.notes.map((n) => (
                                    <div key={n} className="text-xs text-slate-700">
                                      • {n}
                                    </div>
                                  ))}
                                </div>
                              </div>
                            </div>

                            <div className="text-xs text-slate-500">
                              Anchor:{" "}
                              <Link className="font-mono underline" href={docsHref(it.key)}>
                                {docsHref(it.key)}
                              </Link>
                            </div>
                          </div>
                        </details>
                      ))}
                    </div>
                  </div>
                ))}
            </div>
          ))}
      </CardContent>
    </Card>
  );
}

export default ToolReferencePanel;
