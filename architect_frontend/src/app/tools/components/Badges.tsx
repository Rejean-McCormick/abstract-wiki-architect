// architect_frontend/src/app/tools/components/Badges.tsx
"use client";

import React from "react";
import { Badge } from "@/components/ui/badge";
import type { Risk } from "../backendRegistry";
import type { Status } from "../classify";

type BadgeProps = {
  className?: string;
};

const base = "text-[10px] leading-4 whitespace-nowrap";

export function RiskBadge({ risk }: { risk: Risk }) {
  if (risk === "heavy") {
    return (
      <Badge variant="destructive" className={base}>
        Heavy
      </Badge>
    );
  }
  if (risk === "moderate") {
    return (
      <Badge
        variant="outline"
        className={`${base} border-amber-500 text-amber-700 bg-amber-50`}
      >
        Caution
      </Badge>
    );
  }
  return (
    <Badge variant="secondary" className={base}>
      Safe
    </Badge>
  );
}

export function StatusBadge({ status }: { status: Status }) {
  if (status === "legacy") {
    return (
      <Badge
        variant="outline"
        className={`${base} border-slate-400 text-slate-600 bg-slate-50`}
      >
        Legacy
      </Badge>
    );
  }
  if (status === "experimental") {
    return (
      <Badge
        variant="outline"
        className={`${base} border-purple-400 text-purple-700 bg-purple-50`}
      >
        Experimental
      </Badge>
    );
  }
  if (status === "internal") {
    return (
      <Badge
        variant="outline"
        className={`${base} border-slate-300 text-slate-500 bg-slate-50`}
      >
        Internal
      </Badge>
    );
  }
  return (
    <Badge
      variant="outline"
      className={`${base} border-emerald-400 text-emerald-700 bg-emerald-50`}
    >
      Active
    </Badge>
  );
}

export function WiringBadge({
  wired,
  hidden,
}: {
  wired: boolean;
  hidden?: boolean;
}) {
  if (!wired) {
    return (
      <Badge
        variant="outline"
        className={`${base} border-slate-300 text-slate-500 bg-slate-50`}
      >
        Not wired
      </Badge>
    );
  }

  if (hidden) {
    return (
      <Badge
        variant="outline"
        className={`${base} border-blue-400 text-blue-700 bg-blue-50`}
      >
        Hidden
      </Badge>
    );
  }

  return (
    <Badge
      variant="outline"
      className={`${base} border-emerald-400 text-emerald-700 bg-emerald-50`}
    >
      Wired
    </Badge>
  );
}
