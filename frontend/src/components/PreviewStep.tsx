import { useEffect, useState } from "react";
import { previewMapping } from "../api";
import type { PreviewResponse, UploadResponse } from "../types";
import { ValidationPanel } from "./ValidationPanel";

interface Props {
  upload: UploadResponse;
  mapping: Record<string, string | null>;
  defaults: Record<string, string>;
  onBack: () => void;
  onContinue: () => void;
}

export function PreviewStep({ upload, mapping, defaults, onBack, onContinue }: Props): JSX.Element {
  const [data, setData] = useState<PreviewResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
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
        if (!cancelled) setData(d);
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
  }, [upload, mapping, defaults]);

  const cols = data?.rows[0] ? Object.keys(data.rows[0]) : [];
  const canExport = !!data && data.summary.error_count === 0;

  return (
    <div className="space-y-4">
      <div className="card p-4 flex items-center justify-between gap-4 flex-wrap">
        <div className="text-sm">
          <div className="font-semibold">Preview & validate</div>
          <div className="text-xs text-devoteam-slate">
            {loading
              ? "Computing preview…"
              : data
              ? `${data.summary.total_rows} rows · ${data.summary.error_count} errors · ${data.summary.warning_count} warnings · ${data.summary.distinct_machine_names} unique names`
              : ""}
          </div>
        </div>
        <div className="flex gap-2">
          <button className="btn-ghost" onClick={onBack}>← Adjust mapping</button>
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

      {data && (
        <>
          <ValidationPanel issues={data.issues} />

          <div className="card overflow-hidden">
            <div className="px-4 py-3 border-b border-devoteam-line bg-devoteam-mist/50 text-xs uppercase tracking-wide text-devoteam-slate">
              Transformed preview (first {data.rows.length} rows)
            </div>
            <div className="overflow-x-auto max-h-[28rem]">
              <table className="min-w-full text-xs">
                <thead className="bg-white sticky top-0">
                  <tr>
                    {cols.map((c) => (
                      <th key={c} className="px-3 py-2 text-left font-medium text-devoteam-slate border-b border-devoteam-line">
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.rows.map((row, idx) => (
                    <tr key={idx} className="even:bg-devoteam-mist/30">
                      {cols.map((c) => (
                        <td key={c} className="px-3 py-1.5 border-b border-devoteam-line/50 font-mono whitespace-nowrap">
                          {String((row as Record<string, unknown>)[c] ?? "")}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
