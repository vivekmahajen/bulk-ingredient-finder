/**
 * Parse a pasted/uploaded ingredient table into API-ready `IngredientCreate`
 * rows. Two shapes are supported:
 *
 *  1. Header-mapped — the first row names the columns (e.g. a forecast
 *     spreadsheet with `Ingredient, Jan…Dec, Annual, Category, Purchase as,
 *     Order cadence, Recommended vendor, Website`). Columns are matched by name;
 *     monthly demand + annual + per-serving + vendor + website are collected into
 *     an optional `forecast`. Only the ingredient name is required — category,
 *     unit, and cadence are inferred or defaulted.
 *  2. Positional — no header: `name, category, unit, frequency?, language?,
 *     par_level?` (tab- or comma-separated).
 */

import {
  CATEGORIES,
  DEFAULT_UNITS,
  FREQUENCIES,
  type Category,
  type DefaultUnit,
  type PurchaseFrequency,
} from "@/lib/types";

export interface ForecastData {
  jan?: number | null;
  feb?: number | null;
  mar?: number | null;
  apr?: number | null;
  may?: number | null;
  jun?: number | null;
  jul?: number | null;
  aug?: number | null;
  sep?: number | null;
  oct?: number | null;
  nov?: number | null;
  dec?: number | null;
  annual?: number | null;
  g_ml_per_serving?: number | null;
  recommended_vendor?: string | null;
  vendor_website?: string | null;
}

export interface IngredientCreate {
  display_name: string;
  source_lang?: string | null;
  category?: Category;
  default_unit?: DefaultUnit;
  purchase_frequency?: PurchaseFrequency;
  par_level?: number | null;
  notes?: string | null;
  forecast?: ForecastData;
}

export interface PreviewRow {
  raw: string;
  parsed?: IngredientCreate;
  error?: string;
}

export interface ParseResult {
  headerMapped: boolean;
  rows: PreviewRow[];
}

const FREQ_VALUES = FREQUENCIES.map((f) => f.value) as readonly string[];

type MonthKey =
  | "jan"
  | "feb"
  | "mar"
  | "apr"
  | "may"
  | "jun"
  | "jul"
  | "aug"
  | "sep"
  | "oct"
  | "nov"
  | "dec";

const MONTHS: ReadonlyArray<readonly [MonthKey, readonly string[]]> = [
  ["jan", ["jan", "january"]],
  ["feb", ["feb", "february"]],
  ["mar", ["mar", "march"]],
  ["apr", ["apr", "april"]],
  ["may", ["may"]],
  ["jun", ["jun", "june"]],
  ["jul", ["jul", "july"]],
  ["aug", ["aug", "august"]],
  ["sep", ["sep", "sept", "september"]],
  ["oct", ["oct", "october"]],
  ["nov", ["nov", "november"]],
  ["dec", ["dec", "december"]],
];

function detectDelimiter(line: string): "\t" | "," {
  return line.includes("\t") ? "\t" : ",";
}

/** Split a row, honoring RFC-4180 double-quotes for comma-delimited input. */
function splitRow(line: string, delim: "\t" | ","): string[] {
  if (delim === "\t") return line.split("\t");
  const out: string[] = [];
  let cur = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (inQuotes) {
      if (c === '"') {
        if (line[i + 1] === '"') {
          cur += '"';
          i++;
        } else inQuotes = false;
      } else cur += c;
    } else if (c === '"') {
      inQuotes = true;
    } else if (c === ",") {
      out.push(cur);
      cur = "";
    } else cur += c;
  }
  out.push(cur);
  return out;
}

export function normalizeCategory(value: string): Category | null {
  const s = value.trim().toLowerCase();
  return (CATEGORIES as readonly string[]).includes(s) ? (s as Category) : null;
}

/** Map a free-text order cadence ("2×/week", "Weekly", "Monthly", …). */
export function normalizeFrequency(value: string): PurchaseFrequency {
  const s = value.trim().toLowerCase().replace(/\s+/g, "");
  if (/(2|two|twice)[x×]?\/?(week|wk)/.test(s)) return "twice_weekly";
  if (/daily|everyday/.test(s)) return "daily";
  if (/biweek|fortnight|every2week/.test(s)) return "biweekly";
  if (/month/.test(s)) return "monthly";
  if (/quarter/.test(s)) return "quarterly";
  if (/week/.test(s)) return "weekly";
  return "weekly";
}

/** Infer the base unit from a pack description ("40 lb case", "Gallon", …). */
export function inferUnit(purchaseAs: string): DefaultUnit {
  const s = purchaseAs.toLowerCase();
  if (/gallon|quart|litre|liter|(^|\s)ml(\s|$)|(^|\s)l(\s|$)/.test(s)) return "l";
  if (/\bkg\b|gram|(^|\s)g(\s|$)|\blb\b|\boz\b|pound|bulk|block|jug/.test(s)) return "kg";
  if (/case/.test(s)) return "case";
  if (/bag|sack/.test(s)) return "bag";
  return "each";
}

/** Parse a numeric cell, tolerating thousands separators ("1,133" → 1133). */
function num(value: string | undefined): number | null {
  if (value === undefined) return null;
  const t = value.trim().replace(/,/g, "");
  if (t === "") return null;
  const n = Number(t);
  return Number.isFinite(n) ? n : null;
}

interface HeaderCols {
  name: number;
  category: number;
  cadence: number;
  purchase: number;
  serving: number;
  vendor: number;
  website: number;
  annual: number;
  months: number[]; // 12 indices (jan..dec), -1 when absent
}

function findCol(headers: string[], ...needles: string[]): number {
  const lower = headers.map((h) => h.trim().toLowerCase());
  for (const needle of needles) {
    const i = lower.findIndex((h) => h.includes(needle));
    if (i >= 0) return i;
  }
  return -1;
}

function findExact(headers: string[], names: readonly string[]): number {
  const lower = headers.map((h) => h.trim().toLowerCase());
  return lower.findIndex((h) => names.includes(h));
}

function buildForecast(
  cells: string[],
  cols: HeaderCols,
  serving: string,
  vendor: string,
  website: string,
): ForecastData | undefined {
  const forecast: ForecastData = {};
  let has = false;

  MONTHS.forEach(([key], mi) => {
    const idx = cols.months[mi];
    const v = num(idx >= 0 ? cells[idx] : undefined);
    if (v !== null) {
      forecast[key] = v;
      has = true;
    }
  });

  const annual = num(cols.annual >= 0 ? cells[cols.annual] : undefined);
  if (annual !== null) {
    forecast.annual = annual;
    has = true;
  }
  const servingNum = num(serving);
  if (servingNum !== null) {
    forecast.g_ml_per_serving = servingNum;
    has = true;
  }
  if (vendor) {
    forecast.recommended_vendor = vendor;
    has = true;
  }
  if (website) {
    forecast.vendor_website = website;
    has = true;
  }
  return has ? forecast : undefined;
}

function parseHeaderRow(line: string, delim: "\t" | ",", cols: HeaderCols): PreviewRow {
  const cells = splitRow(line, delim).map((c) => c.trim());
  const at = (idx: number): string => (idx >= 0 ? (cells[idx] ?? "") : "");

  const name = at(cols.name);
  if (name.length === 0) return { raw: line, error: "name is required" };

  const parsed: IngredientCreate = { display_name: name };

  const category = normalizeCategory(at(cols.category)); // valid → use; else default server-side
  if (category !== null) parsed.category = category;

  const purchaseAs = at(cols.purchase);
  if (purchaseAs) {
    parsed.default_unit = inferUnit(purchaseAs);
    parsed.notes = `Purchase as: ${purchaseAs}`;
  }

  const cadence = at(cols.cadence);
  if (cadence) parsed.purchase_frequency = normalizeFrequency(cadence);

  const forecast = buildForecast(cells, cols, at(cols.serving), at(cols.vendor), at(cols.website));
  if (forecast) parsed.forecast = forecast;

  const summary = [name, category ?? "—", parsed.default_unit ?? "—", parsed.purchase_frequency ?? "—"];
  if (forecast?.annual != null) summary.push(`≈${forecast.annual}/yr`);
  return { raw: summary.join("  ·  "), parsed };
}

function parsePositional(line: string, delim: "\t" | ","): PreviewRow {
  const cells = splitRow(line, delim).map((c) => c.trim());
  const [name, catStr, unitStr, freqStr, langStr, parStr] = cells;

  if (name === undefined || name.length === 0) return { raw: line, error: "name is required" };
  const parsed: IngredientCreate = { display_name: name };

  if (catStr !== undefined && catStr.length > 0) {
    const category = normalizeCategory(catStr);
    if (category === null) return { raw: line, error: `unknown category "${catStr}"` };
    parsed.category = category;
  }
  if (unitStr !== undefined && unitStr.length > 0) {
    if (!(DEFAULT_UNITS as readonly string[]).includes(unitStr))
      return { raw: line, error: `unit must be one of ${DEFAULT_UNITS.join(", ")}` };
    parsed.default_unit = unitStr as DefaultUnit;
  }
  if (freqStr !== undefined && freqStr.length > 0) {
    if (!FREQ_VALUES.includes(freqStr))
      return { raw: line, error: `frequency must be one of ${FREQ_VALUES.join(", ")}` };
    parsed.purchase_frequency = freqStr as PurchaseFrequency;
  }
  if (parStr !== undefined && parStr.length > 0) {
    const n = Number(parStr);
    if (!Number.isFinite(n) || n < 0) return { raw: line, error: "par_level must be a number ≥ 0" };
    parsed.par_level = n;
  }
  if (langStr !== undefined && langStr.length > 0) parsed.source_lang = langStr;

  return { raw: line, parsed };
}

/** True when the first row looks like column headers rather than data. */
function looksLikeHeader(cells: string[]): boolean {
  const lower = cells.map((c) => c.trim().toLowerCase());
  return lower.some((c) => c === "ingredient" || c === "name") && lower.includes("category");
}

export function parseIngredientTable(text: string): ParseResult {
  const lines = text
    .split("\n")
    .map((l) => l.replace(/\r$/, ""))
    .filter((l) => l.trim().length > 0);
  if (lines.length === 0) return { headerMapped: false, rows: [] };

  const delim = detectDelimiter(lines[0]);
  const firstCells = splitRow(lines[0], delim).map((c) => c.trim());

  if (looksLikeHeader(firstCells)) {
    const cols: HeaderCols = {
      name: findCol(firstCells, "ingredient", "name"),
      category: findCol(firstCells, "category"),
      cadence: findCol(firstCells, "order cadence", "cadence", "frequency"),
      purchase: findCol(firstCells, "purchase as", "purchase", "pack"),
      serving: findCol(firstCells, "per serving", "serving"),
      vendor: findCol(firstCells, "recommended vendor", "vendor", "supplier"),
      website: findCol(firstCells, "website", "url", "site"),
      annual: findExact(firstCells, ["annual", "annual total", "total"]),
      months: MONTHS.map(([, names]) => findExact(firstCells, names)),
    };
    return {
      headerMapped: true,
      rows: lines.slice(1).map((line) => parseHeaderRow(line, delim, cols)),
    };
  }

  return { headerMapped: false, rows: lines.map((line) => parsePositional(line, delim)) };
}
