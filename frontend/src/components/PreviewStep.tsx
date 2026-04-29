import { useEffect, useMemo, useRef, useState } from "react";
import { fetchOsCatalog, previewMapping } from "../api";
import type {
  EditableRow,
  OsCatalog,
  PreviewResponse,
  UploadResponse,
  ValidationIssue,
} from "../types";
import { ValidationPanel } from "./ValidationPanel";

interface Props {
  upload: UploadResponse;
  mapping: Record<string, string | null>;
  defaults: Record<string, string>;
  rows: EditableRow[] | null;
  onRowsChange: (rows: EditableRow[]) => void;
  onBack: () => void;
  onContinue: () => void;
}

// Columns the user is allowed to edit inline. Order matches what's most
// useful to fix first.
const EDITABLE_COLUMNS: { key: string; type: "text" | "number" | "os" | "status"; label: string }[] = [
  { key: "MachineId", type: "text", label: "MachineId" },
  { key: "MachineName", type: "text", label: "MachineName" },
  { key: "OsName", type: "os", label: "OsName" },
  { key: "MachineStatus(optional)", type: "status", label: "Status" },
  { key: "MachineTypeLabel(optional)", type: "text", label: "Type" },
  { key: "AllocatedProcessorCoreCount", type: "number", label: "CPU" },
  { key: "MemoryGiB", type: "number", label: "RAM (GiB)" },
  { key: "TotalDiskAllocatedGiB", type: "number", label: "Disk (GiB)" },
  { key: "PrimaryIPAddress(optional)", type: "text", label: "Primary IP" },
  { key: "IpAddressListSemiColonDelimited(optional)", type: "text", label: "IP list" },
];

const STATUS_OPTIONS = ["", "running", "stopped", "suspended"];

function isGenericOs(value: string, generic: string[]): boolean {
  if (!value) return false;
  return generic.includes(value.trim().toLowerCase());
}

function generateMachineId(seq: number, name: string): string {
  const safe = (name || "").trim().replace(/\s+/g, "-").toUpperCase();
  return `DISC-${String(seq).padStart(3, "0")}-${safe}`;
}

function dedupMachineNames(rows: EditableRow[]): EditableRow[] {
  const seen = new Map<string, number>();
  return rows.map((r) => {
    const name = String(r.MachineName ?? "").trim();
    if (!name) return r;
    const count = seen.get(name) ?? 0;
    seen.set(name, count + 1);
    if (count === 0) return r;
    return { ...r, MachineName: `${name}-${String(count + 1).padStart(2, "0")}` };
  });
}

export function PreviewStep({
  upload,
  mapping,
  defaults,
  rows,
  onRowsChange,
  onBack,
  onContinue,
}: Props): JSX.Element {
  const [data, setData] = useState<PreviewResponse | null>(null);
  const [loading, setLoading] = useState(rows === null);
  const [revalidating, setRevalidating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [catalog, setCatalog] = useState<OsCatalog | null>(null);
  const [bulkOs, setBulkOs] = useState<string>("");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [filterSourceOs, setFilterSourceOs] = useState<string>("");

  // Cell refs so the validation panel can scroll to a specific row+col.
  const cellRefs = useRef<Map<string, HTMLElement>>(new Map());
  const rowRefs = useRef<Map<number, HTMLTableRowElement>>(new Map());

  // Initial load: fetch transformed rows (only when caller hasn't passed rows yet).
  useEffect(() => {
    fetchOsCatalog().then(setCatalog).catch(() => {});
  }, []);

  useEffect(() => {
    if (rows !== null) return; // already have edited rows from prior visit
    let cancelled = false;
    setLoading(true);
    previewMapping({
      upload_id: upload.upload_id,
      selected_sheet: upload.selected_sheet,
      header_row_index: upload.header_row_index,
      mapping,
      defaults,
    })
      .then((d) => {
        if (cancelled) return;
        setData(d);
        // Annotate each row with its source OS for bulk-by-source actions
        const sourceOsCol = mapping.OsName;
        const sampleByName = new Map<string, unknown>();
        if (sourceOsCol) {
          for (const sr of upload.sample_rows) {
            const key = String((sr as Record<string, unknown>)[mapping.MachineName ?? ""] ?? "");
            if (key) sampleByName.set(key, (sr as Record<string, unknown>)[sourceOsCol]);
          }
        }
        const annotated: EditableRow[] = d.rows.map((r) => {
          const name = String(r.MachineName ?? "");
          return { ...r, _source_os: String(sampleByName.get(name) ?? r.OsName ?? "") } as EditableRow;
        });
        onRowsChange(annotated);
      })
      .catch((e) => {
        if (!cancelled) setError((e as Error).message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [upload.upload_id]);

  // Re-validate the current rows against the backend whenever the user clicks
  // the Revalidate button or applies a bulk action. Sends only the rows; the
  // server skips re-parsing + re-transformation.
  const revalidate = async (nextRows: EditableRow[] = rows ?? []) => {
    setRevalidating(true);
    setError(null);
    try {
      const d = await previewMapping({
        upload_id: upload.upload_id,
        selected_sheet: upload.selected_sheet,
        header_row_index: upload.header_row_index,
        mapping,
        defaults,
        rows: nextRows,
      });
      setData(d);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setRevalidating(false);
    }
  };

  const setCell = (rowIdx: number, key: string, value: string | number) => {
    if (!rows) return;
    const next = rows.map((r, i) => (i === rowIdx ? { ...r, [key]: value } : r));
    onRowsChange(next);
  };

  const sourceOsValues = useMemo(() => {
    const set = new Set<string>();
    (rows ?? []).forEach((r) => {
      const v = String(r._source_os ?? "").trim();
      if (v) set.add(v);
    });
    return Array.from(set).sort();
  }, [rows]);

  // Index issues by row for fast cell highlighting
  const issuesByCell = useMemo(() => {
    const map = new Map<string, ValidationIssue[]>();
    (data?.issues ?? []).forEach((i) => {
      const k = `${i.row - 1}|${i.target_column}`;
      const arr = map.get(k) ?? [];
      arr.push(i);
      map.set(k, arr);
    });
    return map;
  }, [data?.issues]);

  const issuesByRow = useMemo(() => {
    const map = new Map<number, ValidationIssue[]>();
    (data?.issues ?? []).forEach((i) => {
      const arr = map.get(i.row - 1) ?? [];
      arr.push(i);
      map.set(i.row - 1, arr);
    });
    return map;
  }, [data?.issues]);

  const cellSeverity = (rowIdx: number, key: string): "error" | "warning" | null => {
    const arr = issuesByCell.get(`${rowIdx}|${key}`);
    if (!arr || arr.length === 0) return null;
    return arr.some((i) => i.severity === "error") ? "error" : "warning";
  };

  const focusIssue = (i: ValidationIssue) => {
    const idx = i.row - 1;
    const cellKey = `${idx}|${i.target_column}`;
    const el = cellRefs.current.get(cellKey) ?? rowRefs.current.get(idx);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      const focusable = (el as HTMLElement).querySelector<HTMLElement>("input,select,textarea");
      if (focusable) focusable.focus();
    }
  };

  // Bulk actions
  const applyOsToMissing = () => {
    if (!rows || !bulkOs) return;
    const next = rows.map((r) => (String(r.OsName ?? "").trim() ? r : { ...r, OsName: bulkOs }));
    onRowsChange(next);
    void revalidate(next);
  };

  const applyOsToBySource = () => {
    if (!rows || !bulkOs || !filterSourceOs) return;
    const fs = filterSourceOs.toLowerCase();
    const next = rows.map((r) =>
      String(r._source_os ?? "").toLowerCase() === fs ? { ...r, OsName: bulkOs } : r
    );
    onRowsChange(next);
    void revalidate(next);
  };

  const applyOsToSelected = () => {
    if (!rows || !bulkOs || selected.size === 0) return;
    const next = rows.map((r, i) => (selected.has(i) ? { ...r, OsName: bulkOs } : r));
    onRowsChange(next);
    void revalidate(next);
  };

  const fillMissingMachineIds = () => {
    if (!rows) return;
    const next = rows.map((r, i) =>
      String(r.MachineId ?? "").trim()
        ? r
        : { ...r, MachineId: generateMachineId(i + 1, String(r.MachineName ?? "")) }
    );
    onRowsChange(next);
    void revalidate(next);
  };

  const dedupNames = () => {
    if (!rows) return;
    const next = dedupMachineNames(rows);
    onRowsChange(next);
    void revalidate(next);
  };

  const toggleRow = (i: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  };
  const toggleAll = () => {
    if (!rows) return;
    if (selected.size === rows.length) setSelected(new Set());
    else setSelected(new Set(rows.map((_, i) => i)));
  };

  const summary = data?.summary;
  const canExport = !!summary && summary.error_count === 0;

  return (
    <div className="space-y-4">
      <div className="card p-4 flex items-center justify-between gap-4 flex-wrap">
        <div className="text-sm">
          <div className="font-semibold">Preview & validate</div>
          <div className="text-xs text-devoteam-slate">
            {loading
              ? "Computing initial preview…"
              : summary
              ? `${summary.total_rows} rows · ${summary.error_count} errors · ${summary.warning_count} warnings · ${summary.distinct_machine_names} unique names`
              : ""}
            {revalidating && <span className="ml-2 text-orange-600">revalidating…</span>}
          </div>
        </div>
        <div className="flex gap-2 flex-wrap">
          <button className="btn-ghost" onClick={onBack}>← Adjust mapping</button>
          <button className="btn-ghost" onClick={() => void revalidate()} disabled={revalidating || !rows}>
            Revalidate
          </button>
          <button
            className="btn-primary"
            disabled={!canExport}
            onClick={onContinue}
            title={canExport ? "" : "Resolve all errors before export"}
          >
            Continue to export →
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>
      )}

      {/* Bulk action toolbar */}
      <div className="card p-4 space-y-3">
        <div className="text-xs uppercase tracking-wide text-devoteam-slate">Bulk fixes</div>
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[260px]">
            <label className="field-label">Pick a canonical GCE OS</label>
            <select className="input" value={bulkOs} onChange={(e) => setBulkOs(e.target.value)}>
              <option value="">— select OS —</option>
              {catalog && (
                <>
                  <optgroup label="Windows">
                    {catalog.options.filter((o) => o.type === "WINDOWS").map((o) => (
                      <option key={o.name} value={o.name}>{o.name}</option>
                    ))}
                  </optgroup>
                  <optgroup label="Linux">
                    {catalog.options.filter((o) => o.type === "LINUX").map((o) => (
                      <option key={o.name} value={o.name}>{o.name}</option>
                    ))}
                  </optgroup>
                </>
              )}
            </select>
          </div>
          <button className="btn-ghost" onClick={applyOsToMissing} disabled={!bulkOs}>
            Apply to rows w/ missing OsName
          </button>
          <div className="flex items-end gap-1">
            <div>
              <label className="field-label">Source OS equals</label>
              <select className="input" value={filterSourceOs} onChange={(e) => setFilterSourceOs(e.target.value)}>
                <option value="">— pick —</option>
                {sourceOsValues.map((v) => <option key={v} value={v}>{v}</option>)}
              </select>
            </div>
            <button className="btn-ghost" onClick={applyOsToBySource} disabled={!bulkOs || !filterSourceOs}>
              Apply to matching
            </button>
          </div>
          <button className="btn-ghost" onClick={applyOsToSelected} disabled={!bulkOs || selected.size === 0}>
            Apply to selected ({selected.size})
          </button>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="btn-ghost" onClick={fillMissingMachineIds}>Auto-generate missing MachineId</button>
          <button className="btn-ghost" onClick={dedupNames}>Deduplicate MachineName (-02, -03…)</button>
        </div>
      </div>

      {data && <ValidationPanel issues={data.issues} onIssueClick={focusIssue} />}

      {/* Editable preview table */}
      <div className="card overflow-hidden">
        <div className="px-4 py-3 border-b border-devoteam-line bg-devoteam-mist/50 text-xs uppercase tracking-wide text-devoteam-slate flex justify-between">
          <span>Editable preview ({rows?.length ?? 0} rows)</span>
          <span className="text-devoteam-slate/70">Edit cells inline · Revalidate to refresh issues</span>
        </div>
        <div className="overflow-x-auto max-h-[34rem]">
          <table className="min-w-full text-xs">
            <thead className="bg-white sticky top-0 z-10">
              <tr>
                <th className="px-2 py-2 border-b border-devoteam-line">
                  <input
                    type="checkbox"
                    checked={!!rows && selected.size === rows.length && rows.length > 0}
                    onChange={toggleAll}
                  />
                </th>
                <th className="px-2 py-2 text-left text-devoteam-slate border-b border-devoteam-line">#</th>
                {EDITABLE_COLUMNS.map((c) => (
                  <th key={c.key} className="px-2 py-2 text-left font-medium text-devoteam-slate border-b border-devoteam-line">
                    {c.label}
                  </th>
                ))}
                <th className="px-2 py-2 text-left text-devoteam-slate border-b border-devoteam-line">Source OS</th>
              </tr>
            </thead>
            <tbody>
              {(rows ?? []).map((row, idx) => {
                const rowIssues = issuesByRow.get(idx);
                const rowHasError = rowIssues?.some((i) => i.severity === "error") ?? false;
                return (
                  <tr
                    key={idx}
                    ref={(el) => {
                      if (el) rowRefs.current.set(idx, el);
                    }}
                    className={`border-b border-devoteam-line/40 ${rowHasError ? "bg-red-50/40" : "even:bg-devoteam-mist/30"}`}
                  >
                    <td className="px-2 py-1 text-center">
                      <input type="checkbox" checked={selected.has(idx)} onChange={() => toggleRow(idx)} />
                    </td>
                    <td className="px-2 py-1 text-devoteam-slate">{idx + 1}</td>
                    {EDITABLE_COLUMNS.map((c) => {
                      const sev = cellSeverity(idx, c.key);
                      const cellClass =
                        sev === "error"
                          ? "border-red-400 bg-red-50"
                          : sev === "warning"
                          ? "border-amber-400 bg-amber-50"
                          : "border-devoteam-line";
                      const value = row[c.key] ?? "";
                      return (
                        <td
                          key={c.key}
                          ref={(el) => {
                            if (el) cellRefs.current.set(`${idx}|${c.key}`, el);
                          }}
                          className="px-1 py-0.5 align-top"
                        >
                          {c.type === "os" ? (
                            <OsCell
                              value={String(value)}
                              catalog={catalog}
                              sourceOs={String(row._source_os ?? "")}
                              onChange={(v) => setCell(idx, c.key, v)}
                              cellClass={cellClass}
                            />
                          ) : c.type === "status" ? (
                            <select
                              className={`w-full rounded border px-2 py-1 text-xs ${cellClass}`}
                              value={String(value)}
                              onChange={(e) => setCell(idx, c.key, e.target.value)}
                            >
                              {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s || "(empty)"}</option>)}
                            </select>
                          ) : c.type === "number" ? (
                            <input
                              type="number"
                              className={`w-24 rounded border px-2 py-1 text-xs ${cellClass}`}
                              value={String(value)}
                              onChange={(e) => setCell(idx, c.key, e.target.value)}
                            />
                          ) : (
                            <input
                              type="text"
                              className={`w-full min-w-[10rem] rounded border px-2 py-1 text-xs font-mono ${cellClass}`}
                              value={String(value)}
                              onChange={(e) => setCell(idx, c.key, e.target.value)}
                            />
                          )}
                        </td>
                      );
                    })}
                    <td className="px-2 py-1 text-devoteam-slate font-mono">
                      {String(row._source_os ?? "")}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function OsCell({
  value,
  catalog,
  sourceOs,
  onChange,
  cellClass,
}: {
  value: string;
  catalog: OsCatalog | null;
  sourceOs: string;
  onChange: (v: string) => void;
  cellClass: string;
}): JSX.Element {
  const isGeneric = catalog ? isGenericOs(value, catalog.generic_values) : false;
  const isMissing = !value;
  const suggestionKey = (sourceOs || value || "").trim().toLowerCase();
  const suggestions =
    catalog?.suggestions?.[suggestionKey] ??
    (suggestionKey
      ? catalog?.suggestions?.[
          Object.keys(catalog.suggestions).find((k) => suggestionKey.includes(k)) ?? ""
        ]
      : undefined);

  return (
    <div className="space-y-1">
      <select
        className={`w-full min-w-[16rem] rounded border px-2 py-1 text-xs ${cellClass}`}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">— select OS —</option>
        {value && !catalog?.options.some((o) => o.name === value) && (
          // Preserve the current value as an option so users see what they had
          <option value={value}>{value} (non-canonical)</option>
        )}
        {catalog && (
          <>
            <optgroup label="Windows">
              {catalog.options.filter((o) => o.type === "WINDOWS").map((o) => (
                <option key={o.name} value={o.name}>{o.name}</option>
              ))}
            </optgroup>
            <optgroup label="Linux">
              {catalog.options.filter((o) => o.type === "LINUX").map((o) => (
                <option key={o.name} value={o.name}>{o.name}</option>
              ))}
            </optgroup>
          </>
        )}
      </select>
      {(isGeneric || isMissing) && suggestions && suggestions.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {suggestions.slice(0, 3).map((s) => (
            <button
              key={s}
              className="rounded bg-devoteam-mist px-2 py-0.5 text-[10px] text-devoteam-ink hover:bg-devoteam-line"
              onClick={() => onChange(s)}
              title={`Apply suggestion: ${s}`}
            >
              {s}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
