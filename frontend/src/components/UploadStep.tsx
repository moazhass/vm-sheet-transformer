import { useCallback, useRef, useState } from "react";
import { uploadFile } from "../api";
import type { TemplateColumns, UploadResponse } from "../types";

interface Props {
  template: TemplateColumns | null;
  onUploaded: (u: UploadResponse) => void;
}

export function UploadStep({ template, onUploaded }: Props): JSX.Element {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const submit = useCallback(
    async (file: File) => {
      setError(null);
      setBusy(true);
      try {
        const res = await uploadFile(file);
        onUploaded(res);
      } catch (err) {
        const e = err as Error & { detail?: unknown };
        const msg = typeof e.detail === "string" ? e.detail : (e as Error).message;
        setError(msg || "Upload failed");
      } finally {
        setBusy(false);
      }
    },
    [onUploaded]
  );

  return (
    <div className="grid lg:grid-cols-3 gap-6">
      <div className="lg:col-span-2 card p-6">
        <h2 className="text-lg font-semibold mb-1">Upload discovery sheet</h2>
        <p className="text-sm text-devoteam-slate mb-4">
          Accepts <b>.csv</b>, <b>.xlsx</b>, or <b>.xls</b>. The first sheet is auto-selected; you can
          change it on the next step.
        </p>

        <div
          className={`border-2 border-dashed rounded-lg p-10 text-center transition ${
            dragOver ? "border-devoteam-accent bg-orange-50" : "border-devoteam-line bg-devoteam-mist/30"
          }`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            const f = e.dataTransfer.files?.[0];
            if (f) void submit(f);
          }}
        >
          <div className="text-sm text-devoteam-slate mb-3">
            Drag and drop a file here, or
          </div>
          <button
            className="btn-primary"
            disabled={busy}
            onClick={() => inputRef.current?.click()}
          >
            {busy ? "Uploading…" : "Choose file"}
          </button>
          <input
            ref={inputRef}
            type="file"
            accept=".csv,.xlsx,.xls"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void submit(f);
              e.target.value = "";
            }}
          />
        </div>

        {error && (
          <div className="mt-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}
      </div>

      <aside className="card p-6">
        <h3 className="font-semibold mb-2 text-sm">Target schema</h3>
        <p className="text-xs text-devoteam-slate mb-3">
          The export will always contain exactly these {template?.target_columns.length ?? 19} columns
          in this order. Required columns are highlighted.
        </p>
        <ul className="space-y-1 text-xs">
          {(template?.target_columns ?? []).map((c) => {
            const required = (template?.required_columns ?? []).includes(c);
            return (
              <li
                key={c}
                className={`flex items-center justify-between rounded px-2 py-1 ${
                  required ? "bg-orange-50 text-devoteam-ink" : "text-devoteam-slate"
                }`}
              >
                <span className="font-mono">{c}</span>
                {required && <span className="badge bg-devoteam-accent text-white">required</span>}
              </li>
            );
          })}
        </ul>
      </aside>
    </div>
  );
}
