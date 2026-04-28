import { useMemo } from "react";
import type { TemplateColumns, UploadResponse } from "../types";

interface Props {
  upload: UploadResponse;
  template: TemplateColumns;
  mapping: Record<string, string | null>;
  defaults: Record<string, string>;
  onMappingChange: (m: Record<string, string | null>) => void;
  onDefaultsChange: (d: Record<string, string>) => void;
  onContinue: () => void;
  onBack: () => void;
}

const DEFAULT_FIELDS: { target: string; type: "text" | "select"; options?: string[] }[] = [
  { target: "IsPhysical", type: "select", options: ["0", "1"] },
  { target: "MachineStatus(optional)", type: "select", options: ["", "running", "stopped", "suspended"] },
  { target: "OsName", type: "select", options: ["", "Windows", "Linux"] },
  { target: "HostingLocation(optional)", type: "text" },
];

function confidenceBadge(c: number): { label: string; cls: string } {
  if (c >= 0.85) return { label: `${Math.round(c * 100)}%`, cls: "bg-emerald-100 text-emerald-800" };
  if (c >= 0.7) return { label: `${Math.round(c * 100)}%`, cls: "bg-amber-100 text-amber-800" };
  if (c > 0) return { label: `${Math.round(c * 100)}%`, cls: "bg-rose-100 text-rose-800" };
  return { label: "—", cls: "bg-devoteam-mist text-devoteam-slate" };
}

export function MappingStep({
  upload,
  template,
  mapping,
  defaults,
  onMappingChange,
  onDefaultsChange,
  onContinue,
  onBack,
}: Props): JSX.Element {
  const required = useMemo(() => new Set(template.required_columns), [template]);

  const setMap = (target: string, source: string | null) => {
    onMappingChange({ ...mapping, [target]: source });
  };

  const setDefault = (target: string, value: string) => {
    onDefaultsChange({ ...defaults, [target]: value });
  };

  const requiredMissing = template.target_columns.filter((c) => {
    if (!required.has(c)) return false;
    if (c === "MachineId") return false; // can be generated
    if (mapping[c]) return false;
    if (defaults[c]) return false;
    return true;
  });

  return (
    <div className="space-y-6">
      <div className="card p-4 flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div className="text-sm">
          <div>
            <span className="font-semibold">{upload.filename}</span>
            <span className="text-devoteam-slate"> · {upload.row_count} rows · {upload.source_columns.length} columns</span>
          </div>
          <div className="text-xs text-devoteam-slate mt-1">
            Sheet: <span className="font-mono">{upload.selected_sheet}</span> · header row index: {upload.header_row_index}
          </div>
        </div>
        <div className="flex gap-2">
          <button className="btn-ghost" onClick={onBack}>← Back</button>
          <button
            className="btn-primary"
            disabled={requiredMissing.length > 0}
            onClick={onContinue}
            title={requiredMissing.length ? `Missing: ${requiredMissing.join(", ")}` : ""}
          >
            Preview & validate →
          </button>
        </div>
      </div>

      {requiredMissing.length > 0 && (
        <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
          <b>Required fields not yet mapped:</b> {requiredMissing.join(", ")}.
          Provide a source mapping or set a default below.
        </div>
      )}

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 card overflow-hidden">
          <div className="px-4 py-3 border-b border-devoteam-line bg-devoteam-mist/50 text-xs uppercase tracking-wide text-devoteam-slate flex">
            <div className="w-2/5">Target column</div>
            <div className="w-2/5">Source column</div>
            <div className="w-1/5 text-right">Confidence</div>
          </div>
          <ul className="divide-y divide-devoteam-line">
            {template.target_columns.map((target) => {
              const sugg = upload.suggested_mapping[target];
              const isReq = required.has(target);
              const conf = confidenceBadge(sugg?.confidence ?? 0);
              return (
                <li key={target} className="px-4 py-3 flex items-center text-sm gap-2">
                  <div className="w-2/5">
                    <div className="font-mono">{target}</div>
                    <div className="text-xs text-devoteam-slate">
                      {isReq ? <span className="text-devoteam-accent font-medium">required · </span> : ""}
                      {sugg?.rationale}
                    </div>
                  </div>
                  <div className="w-2/5">
                    <select
                      className="input"
                      value={mapping[target] ?? ""}
                      onChange={(e) => setMap(target, e.target.value || null)}
                    >
                      <option value="">— unmapped —</option>
                      {target === "MachineId" && (
                        <option value="">Generate (DISC-NNN-MachineName)</option>
                      )}
                      {upload.source_columns.map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="w-1/5 text-right">
                    <span className={`badge ${conf.cls}`}>{conf.label}</span>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>

        <aside className="card p-4 space-y-4 h-fit">
          <div>
            <h3 className="font-semibold text-sm mb-1">Default values</h3>
            <p className="text-xs text-devoteam-slate">
              Used for any row where the mapped source cell is empty.
            </p>
          </div>
          {DEFAULT_FIELDS.map((f) => (
            <div key={f.target}>
              <label className="field-label">{f.target}</label>
              {f.type === "select" ? (
                <select
                  className="input"
                  value={defaults[f.target] ?? ""}
                  onChange={(e) => setDefault(f.target, e.target.value)}
                >
                  {(f.options ?? []).map((o) => (
                    <option key={o} value={o}>
                      {o === "" ? "(none)" : o}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  className="input"
                  type="text"
                  value={defaults[f.target] ?? ""}
                  onChange={(e) => setDefault(f.target, e.target.value)}
                  placeholder="(none)"
                />
              )}
            </div>
          ))}
        </aside>
      </div>

      <div className="card overflow-hidden">
        <div className="px-4 py-3 border-b border-devoteam-line bg-devoteam-mist/50 text-xs uppercase tracking-wide text-devoteam-slate">
          Source sample (first {upload.sample_rows.length} rows)
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-xs">
            <thead className="bg-white">
              <tr>
                {upload.source_columns.map((c) => (
                  <th key={c} className="px-3 py-2 text-left font-medium text-devoteam-slate border-b border-devoteam-line">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {upload.sample_rows.slice(0, 10).map((row, idx) => (
                <tr key={idx} className="even:bg-devoteam-mist/30">
                  {upload.source_columns.map((c) => (
                    <td key={c} className="px-3 py-1.5 border-b border-devoteam-line/50 font-mono">
                      {String((row as Record<string, unknown>)[c] ?? "")}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
