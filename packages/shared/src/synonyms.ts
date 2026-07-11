/**
 * Curated culinary-synonym lookup (TypeScript side).
 *
 * Imports `packages/shared/culinary_synonyms.json` — the single source shared
 * with `apps/api/app/synonyms.py`. A vitest drift test asserts known pairs;
 * because both sides read the same file they cannot diverge.
 */

import raw from "../culinary_synonyms.json";

export interface SynonymTerm {
  alias: string;
  lang: string;
}

export interface SynonymGroup {
  canonical_en: string;
  terms: SynonymTerm[];
}

interface RawFile {
  version: number;
  groups: SynonymGroup[];
}

export const SYNONYM_GROUPS: SynonymGroup[] = (raw as RawFile).groups;

const INDEX: Map<string, SynonymGroup> = (() => {
  const idx = new Map<string, SynonymGroup>();
  for (const group of SYNONYM_GROUPS) {
    idx.set(group.canonical_en.trim().toLowerCase(), group);
    for (const term of group.terms) {
      const key = term.alias.trim().toLowerCase();
      if (!idx.has(key)) idx.set(key, group);
    }
  }
  return idx;
})();

/** Find the group a canonical name OR any alias belongs to (case-insensitive). */
export function findGroup(term: string): SynonymGroup | undefined {
  return INDEX.get(term.trim().toLowerCase());
}
