import { useEffect, useState } from "react";
import { fetchMe, fetchTemplateColumns } from "./api";
import { ExportStep } from "./components/ExportStep";
import { MappingStep } from "./components/MappingStep";
import { PreviewStep } from "./components/PreviewStep";
import { UploadStep } from "./components/UploadStep";
import type { EditableRow, TemplateColumns, UploadResponse, User } from "./types";

type Step = "upload" | "mapping" | "preview" | "export";

const STEP_LABELS: Record<Step, string> = {
  upload: "1 · Upload",
  mapping: "2 · Mapping",
  preview: "3 · Preview & Validate",
  export: "4 · Export",
};

export function App(): JSX.Element {
  const [user, setUser] = useState<User | null>(null);
  const [authError, setAuthError] = useState<string | null>(null);
  const [template, setTemplate] = useState<TemplateColumns | null>(null);
  const [step, setStep] = useState<Step>("upload");
  const [upload, setUpload] = useState<UploadResponse | null>(null);
  const [mapping, setMapping] = useState<Record<string, string | null>>({});
  const [defaults, setDefaults] = useState<Record<string, string>>({
    IsPhysical: "0",
  });
  // Edited rows shared between Preview and Export so manual fixes persist
  // when the user navigates back and forth.
  const [editedRows, setEditedRows] = useState<EditableRow[] | null>(null);

  useEffect(() => {
    fetchMe()
      .then(setUser)
      .catch((err) => {
        if (err.status === 401) setAuthError("login");
        else setAuthError(`Error: ${err.message}`);
      });
    fetchTemplateColumns()
      .then(setTemplate)
      .catch(() => {});
  }, []);

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6">
        <div className="card p-8 max-w-md text-center">
          <div className="text-2xl font-semibold mb-2">Devoteam VM Sheet Transformer</div>
          <p className="text-sm text-devoteam-slate mb-6">
            Sign in with your Devoteam Google account to continue.
          </p>
          {authError === "login" ? (
            <a className="btn-primary w-full" href="/auth/login">
              Sign in with Google
            </a>
          ) : authError ? (
            <div className="text-sm text-red-600">{authError}</div>
          ) : (
            <div className="text-sm text-devoteam-slate">Checking session…</div>
          )}
        </div>
      </div>
    );
  }

  const stepOrder: Step[] = ["upload", "mapping", "preview", "export"];
  const stepIndex = stepOrder.indexOf(step);

  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-devoteam-ink text-white">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div>
            <div className="text-lg font-semibold">VM Sheet Transformer</div>
            <div className="text-xs text-devoteam-mist/80">
              Devoteam internal · transforms discovery sheets into the canonical vmInfo template
            </div>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <span className="opacity-80">{user.email}</span>
            <a href="/auth/logout" className="underline opacity-80 hover:opacity-100">
              Sign out
            </a>
          </div>
        </div>
        <nav className="max-w-6xl mx-auto px-6 pb-4 flex flex-wrap gap-2">
          {stepOrder.map((s, i) => {
            const enabled =
              i <= stepIndex ||
              (s === "mapping" && upload !== null) ||
              (s === "preview" && upload !== null) ||
              (s === "export" && upload !== null);
            const active = s === step;
            return (
              <button
                key={s}
                disabled={!enabled}
                onClick={() => enabled && setStep(s)}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition ${
                  active
                    ? "bg-devoteam-accent text-white"
                    : enabled
                    ? "bg-white/10 hover:bg-white/20 text-white"
                    : "bg-white/5 text-white/40 cursor-not-allowed"
                }`}
              >
                {STEP_LABELS[s]}
              </button>
            );
          })}
        </nav>
      </header>

      <main className="flex-1 max-w-6xl w-full mx-auto p-6">
        {step === "upload" && (
          <UploadStep
            template={template}
            onUploaded={(u) => {
              setUpload(u);
              const initial: Record<string, string | null> = {};
              for (const [target, sugg] of Object.entries(u.suggested_mapping)) {
                initial[target] = sugg.source_column;
              }
              setMapping(initial);
              setEditedRows(null);
              setStep("mapping");
            }}
          />
        )}
        {step === "mapping" && upload && template && (
          <MappingStep
            upload={upload}
            template={template}
            mapping={mapping}
            defaults={defaults}
            onMappingChange={(m) => {
              setMapping(m);
              setEditedRows(null); // mapping changed → invalidate edited rows
            }}
            onDefaultsChange={(d) => {
              setDefaults(d);
              setEditedRows(null);
            }}
            onContinue={() => setStep("preview")}
            onBack={() => setStep("upload")}
          />
        )}
        {step === "preview" && upload && (
          <PreviewStep
            upload={upload}
            mapping={mapping}
            defaults={defaults}
            rows={editedRows}
            onRowsChange={setEditedRows}
            onBack={() => setStep("mapping")}
            onContinue={() => setStep("export")}
          />
        )}
        {step === "export" && upload && (
          <ExportStep
            upload={upload}
            mapping={mapping}
            defaults={defaults}
            rows={editedRows}
            onBack={() => setStep("preview")}
            onReset={() => {
              setUpload(null);
              setMapping({});
              setEditedRows(null);
              setStep("upload");
            }}
          />
        )}
      </main>

      <footer className="border-t border-devoteam-line bg-white">
        <div className="max-w-6xl mx-auto px-6 py-3 text-xs text-devoteam-slate flex justify-between">
          <span>Deterministic transformation — no source data leaves this deployment.</span>
          <span>v1.0.0</span>
        </div>
      </footer>
    </div>
  );
}
