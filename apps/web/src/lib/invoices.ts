/** Invoice-capture domain types + client for PR-9. */

import { apiGet, apiPatch, apiPost, apiUpload, type ApiResult } from "@/lib/api";

export type InvoiceStatus =
  | "uploaded"
  | "extracting"
  | "needs_review"
  | "committed"
  | "failed"
  | "rejected";

export type LineMatchStatus =
  | "auto_matched"
  | "suggested"
  | "unmatched"
  | "manual"
  | "excluded";

export interface InvoiceListItem {
  id: string;
  status: InvoiceStatus;
  vendor_name_raw: string | null;
  invoice_date: string | null;
  stated_total_cents: number | null;
  totals_match: boolean | null;
  line_count: number;
  created_at: string;
}

export interface LineCandidate {
  ingredient_id: string;
  canonical_name_en: string;
  score: number;
}

export interface InvoiceLineRead {
  id: string;
  line_no: number;
  raw_text: string;
  raw_lang: string | null;
  description_en: string | null;
  brand: string | null;
  pack_desc: string | null;
  pack_qty: number | null;
  pack_unit: string | null;
  case_count: number | null;
  unit_price_cents: number | null;
  extended_cents: number | null;
  is_credit: boolean;
  confidence: number;
  match_status: LineMatchStatus;
  matched_ingredient_id: string | null;
  match_score: number | null;
  created_price_entry_id: string | null;
  unit_price_per_base_cents: number | null;
  base_unit: string | null;
  candidates: LineCandidate[];
}

export interface StoreGuess {
  store_id: string;
  name: string;
  score: number;
}

export interface InvoiceRead extends InvoiceListItem {
  invoice_number: string | null;
  currency: string;
  store_id: string | null;
  page_count: number;
  computed_total_cents: number | null;
  extraction_model: string | null;
  extraction_error: string | null;
  committed_at: string | null;
  store_guess: StoreGuess | null;
  signed_image_url: string | null;
  lines: InvoiceLineRead[];
}

export interface InvoiceListResponse {
  items: InvoiceListItem[];
  page: number;
  page_size: number;
  total: number;
}

export interface InvoiceStatusResponse {
  status: InvoiceStatus;
  line_count: number;
}

export interface InvoiceCommitResult {
  invoice_id: string;
  created: number;
  skipped_duplicates: number;
  excluded: number;
  totals_match: boolean;
}

/** Subset of {@link InvoiceLineRead} fields the API accepts on PATCH. */
export interface InvoiceLinePatch {
  raw_text?: string;
  raw_lang?: string | null;
  description_en?: string | null;
  brand?: string | null;
  pack_desc?: string | null;
  pack_qty?: number | null;
  pack_unit?: string | null;
  case_count?: number | null;
  unit_price_cents?: number | null;
  extended_cents?: number | null;
  is_credit?: boolean;
  matched_ingredient_id?: string | null;
  match_status?: LineMatchStatus;
}

/** Pack units offered for line editing — mirrors the price-logging vocabulary. */
export const LINE_PACK_UNITS: readonly string[] = [
  "kg",
  "g",
  "lb",
  "oz",
  "l",
  "ml",
  "gal",
  "each",
];

export interface InvoiceListParams {
  status?: InvoiceStatus;
  page?: number;
  page_size?: number;
}

export async function listInvoices(
  params: InvoiceListParams = {},
): Promise<ApiResult<InvoiceListResponse>> {
  const q = new URLSearchParams();
  if (params.status) q.set("status", params.status);
  if (params.page != null) q.set("page", String(params.page));
  if (params.page_size != null) q.set("page_size", String(params.page_size));
  const qs = q.toString();
  return apiGet<InvoiceListResponse>(`/api/v1/invoices${qs ? `?${qs}` : ""}`);
}

export function getInvoice(id: string): Promise<ApiResult<InvoiceRead>> {
  return apiGet<InvoiceRead>(`/api/v1/invoices/${id}`);
}

export function getInvoiceStatus(id: string): Promise<ApiResult<InvoiceStatusResponse>> {
  return apiGet<InvoiceStatusResponse>(`/api/v1/invoices/${id}/status`);
}

export function patchLine(
  invoiceId: string,
  lineId: string,
  body: InvoiceLinePatch,
): Promise<ApiResult<InvoiceLineRead>> {
  return apiPatch<InvoiceLineRead>(`/api/v1/invoices/${invoiceId}/lines/${lineId}`, body);
}

export function commitInvoice(
  id: string,
  body: { store_id: string; line_ids?: string[] },
): Promise<ApiResult<InvoiceCommitResult>> {
  return apiPost<InvoiceCommitResult>(`/api/v1/invoices/${id}/commit`, body);
}

export function rejectInvoice(id: string): Promise<ApiResult<InvoiceStatusResponse>> {
  return apiPost<InvoiceStatusResponse>(`/api/v1/invoices/${id}/reject`, {});
}

export function uploadInvoice(file: File): Promise<ApiResult<InvoiceRead>> {
  const form = new FormData();
  form.append("file", file);
  return apiUpload<InvoiceRead>("/api/v1/invoices", form);
}

/** True while the backend is still ingesting/extracting an invoice. */
export function isProcessing(status: InvoiceStatus): boolean {
  return status === "uploaded" || status === "extracting";
}

export type ConfidenceBucket = "high" | "medium" | "low";

/** ≥0.9 quiet, 0.7–0.9 amber, <0.7 red — per the review-screen spec. */
export function confidenceBucket(confidence: number): ConfidenceBucket {
  if (confidence >= 0.9) return "high";
  if (confidence >= 0.7) return "medium";
  return "low";
}
