import { useEffect, useState } from "react";
import { downloadBlob, exportFile, previewMapping } from "../api";
import type { EditableRow, PreviewSummary, UploadResponse } from "../types";

interface Props {
  upload: UploadResponse;
  mapping: Record<string, string | null>;
  defaults: Record<string, string>;
  rows: EditableRow[] | null;
  onBack: () => void;
  onReset: () => void;
}

export function ExportStep({ upload, mapping, defaults, rows, onBack, onReset }: Props): JSX.Element {
  const [summary, setSummary] = useState<PreviewSummary | null>(null);
  const [busy, setBusy] = useState<"csv" | "xlsx" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<{ format: "csv" | "xlsx"; rows: number } | null>(null);

  useEffect(() => {
    previewMapping({
      upload_id: upload.upload_id,
      selected_sheet: upload.selected_sheet,
      header_row_index: upload.header_row_index,
      mapping,
      defaults,
      rows: rows ?? undefined,
    })
      .then((d) => setSummary(d.summary))
      .catch((e) => setError((e as Error).message));
  }, [upload, mapping, defaults, rows]);

  const doExport = async (fmt: "csv" | "xlsx") => {
    setError(null);
    setBusy(fmt);
    try {
      const blob = await exportFile({
        upload_id: upload.upload_id,
        selected_sheet: upload.selected_sheet,
        header_row_index: upload.header_row_index,
        mapping,
        defaults,
        rows: rows ?? undefined,
        format: fmt,
      });
      const stem = upload.filename.replace(/\.[^.]+$/, "");
      downloadBlob(blob, `${stem}_vmInfo.${fmt}`);
      setDone({ format: fmt, rows: summary?.total_rows ?? 0 });
    } catch (err) {
      const e = err as Error & { detail?: unknown };
      setError(typeof e.detail === "string" ? e.detail : (e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-4">
      <div className="card p-6">
        <h2 className="text-lg font-semibold mb-1">Export</h2>
        <p className="text-sm text-devoteam-slate mb-4">
          The exported file uses the canonical <span className="font-mono">vmInfo_template.csv</span> schema —
          exactly 19 columns in template order. Empty optional fields are written as empty strings.
        </p>

        {summary && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
            <Stat label="Rows to export" value={summary.total_rows} />
            <Stat label="Unique names" value={summary.distinct_machine_names} />
            <Stat label="Errors" value={summary.error_count} tone={summary.error_count ? "bad" : "neutral"} />
            <Stat label="Warnings" value={summary.warning_count} tone={summary.warning_count ? "warn" : "neutral"} />
          </div>
        )}

        <div className="flex flex-wrap gap-3">
          <button className="btn-primary" onClick={() => doExport("csv")} disabled={busy !== null}>
            {busy === "csv" ? "Exporting…" : "Download CSV"}
          </button>
          <button className="btn-ghost" onClick={() => doExport("xlsx")} disabled={busy !== null}>
            {busy === "xlsx" ? "Exporting…" : "Download XLSX"}
          </button>
          <button className="btn-ghost" onClick={onBack}>← Back to preview</button>
          <button className="btn-ghost" onClick={onReset}>Start over</button>
        </div>

        {done && (
          <div className="mt-4 rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">
            Exported {done.rows} rows as <b>{done.format.toUpperCase()}</b>.
          </div>
        )}
        {error && (
          <div className="mt-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700 whitespace-pre-wrap">
            {error}
          </div>
        )}
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: number;
  tone?: "neutral" | "bad" | "warn";
}): JSX.Element {
  const cls =
    tone === "bad"
      ? "border-red-200 bg-red-50 text-red-700"
      : tone === "warn"
      ? "border-amber-200 bg-amber-50 text-amber-700"
      : "border-devoteam-line bg-white text-devoteam-ink";
  return (
    <div className={`rounded-md border px-3 py-2 ${cls}`}>
      <div className="text-xs uppercase tracking-wide opacity-70">{label}</div>
      <div className="text-2xl font-semibold">{value}</div>
    </div>
  );
}
