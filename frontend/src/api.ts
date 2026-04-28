import type {
  PreviewResponse,
  TemplateColumns,
  UploadResponse,
  User,
} from "./types";

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail: unknown;
    try {
      detail = await res.json();
    } catch {
      detail = await res.text();
    }
    const err = new Error(typeof detail === "string" ? detail : JSON.stringify(detail)) as Error & {
      status?: number;
      detail?: unknown;
    };
    err.status = res.status;
    err.detail = detail;
    throw err;
  }
  return res.json() as Promise<T>;
}

export async function fetchMe(): Promise<User> {
  return handle<User>(await fetch("/api/me", { credentials: "include" }));
}

export async function fetchTemplateColumns(): Promise<TemplateColumns> {
  return handle<TemplateColumns>(await fetch("/api/template-columns", { credentials: "include" }));
}

export async function uploadFile(file: File): Promise<UploadResponse> {
  const fd = new FormData();
  fd.append("file", file);
  return handle<UploadResponse>(
    await fetch("/api/upload", { method: "POST", body: fd, credentials: "include" })
  );
}

export interface PreviewArgs {
  upload_id: string;
  selected_sheet: string;
  header_row_index: number;
  mapping: Record<string, string | null>;
  defaults: Record<string, string>;
}

export async function previewMapping(args: PreviewArgs): Promise<PreviewResponse> {
  return handle<PreviewResponse>(
    await fetch("/api/mapping/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(args),
    })
  );
}

export async function exportFile(args: PreviewArgs & { format: "csv" | "xlsx" }): Promise<Blob> {
  const res = await fetch("/api/export", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(args),
  });
  if (!res.ok) {
    let detail: unknown;
    try {
      detail = await res.json();
    } catch {
      detail = await res.text();
    }
    const err = new Error(
      typeof detail === "string" ? detail : JSON.stringify(detail)
    ) as Error & { status?: number; detail?: unknown };
    err.status = res.status;
    err.detail = detail;
    throw err;
  }
  return res.blob();
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
