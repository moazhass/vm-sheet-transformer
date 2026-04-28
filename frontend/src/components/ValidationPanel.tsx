import { useMemo, useState } from "react";
import type { ValidationIssue } from "../types";

interface Props {
  issues: ValidationIssue[];
}

type Filter = "all" | "error" | "warning";

export function ValidationPanel({ issues }: Props): JSX.Element {
  const [filter, setFilter] = useState<Filter>("all");

  const filtered = useMemo(() => {
    if (filter === "all") return issues;
    return issues.filter((i) => i.severity === filter);
  }, [filter, issues]);

  const errorCount = issues.filter((i) => i.severity === "error").length;
  const warnCount = issues.length - errorCount;

  return (
    <div className="card overflow-hidden">
      <div className="px-4 py-3 border-b border-devoteam-line flex items-center justify-between">
        <div className="text-sm font-semibold">Validation</div>
        <div className="flex gap-1 text-xs">
          {(["all", "error", "warning"] as Filter[]).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-2 py-1 rounded ${
                filter === f ? "bg-devoteam-ink text-white" : "bg-devoteam-mist text-devoteam-slate"
              }`}
            >
              {f === "all" ? `All (${issues.length})` : f === "error" ? `Errors (${errorCount})` : `Warnings (${warnCount})`}
            </button>
          ))}
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="p-4 text-sm text-devoteam-slate">No issues 🎉</div>
      ) : (
        <ul className="divide-y divide-devoteam-line max-h-80 overflow-y-auto">
          {filtered.map((i, idx) => (
            <li key={idx} className="px-4 py-2 text-xs flex items-start gap-3">
              <span
                className={`badge ${
                  i.severity === "error" ? "bg-red-100 text-red-700" : "bg-amber-100 text-amber-700"
                }`}
              >
                {i.severity}
              </span>
              <div>
                <div>
                  <span className="font-mono text-devoteam-ink">row {i.row}</span>{" "}
                  · <span className="font-mono">{i.target_column}</span>
                </div>
                <div className="text-devoteam-slate">{i.message}</div>
                {i.suggested_fix && (
                  <div className="text-devoteam-slate italic">→ {i.suggested_fix}</div>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
