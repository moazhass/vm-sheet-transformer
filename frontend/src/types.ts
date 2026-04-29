export interface MappingSuggestion {
  target_column: string;
  source_column: string | null;
  confidence: number;
  rationale: string;
}

export interface SheetInfo {
  name: string;
  header_row_index: number;
  columns: string[];
  sample_rows: Record<string, unknown>[];
  row_count: number;
}

export interface UploadResponse {
  upload_id: string;
  filename: string;
  sheets: SheetInfo[];
  selected_sheet: string;
  header_row_index: number;
  source_columns: string[];
  sample_rows: Record<string, unknown>[];
  row_count: number;
  suggested_mapping: Record<string, MappingSuggestion>;
}

export interface ValidationIssue {
  row: number;
  target_column: string;
  severity: "error" | "warning";
  message: string;
  suggested_fix?: string;
}

export interface PreviewSummary {
  total_rows: number;
  error_count: number;
  warning_count: number;
  distinct_machine_names: number;
}

export interface PreviewResponse {
  rows: Record<string, unknown>[];
  issues: ValidationIssue[];
  summary: PreviewSummary;
}

export interface TemplateColumns {
  target_columns: string[];
  required_columns: string[];
}

export interface User {
  email: string;
  name: string;
  picture: string;
}

export type OsType = "WINDOWS" | "LINUX" | "UNKNOWN";

export interface OsCatalogEntry {
  name: string;
  type: OsType;
  publisher: string;
  version: string;
}

export interface OsCatalog {
  options: OsCatalogEntry[];
  generic_values: string[];
  suggestions: Record<string, string[]>;
}

/** Row in the editable preview table. Backend canonical columns plus
 * frontend-only `_*` helpers that get stripped before export. */
export type EditableRow = Record<string, string | number | null | undefined>;
