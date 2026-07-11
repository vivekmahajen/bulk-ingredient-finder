"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { searchIngredients, type SearchHit } from "@/lib/search";
import { formatBestPrice } from "@/lib/format";

/** Global ⌘K / Ctrl-K command palette for multilingual ingredient search. */
export function CommandPalette() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [viaTranslation, setViaTranslation] = useState(false);
  const [loading, setLoading] = useState(false);
  const debounce = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((v) => !v);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  const runSearch = useCallback((q: string) => {
    if (debounce.current) clearTimeout(debounce.current);
    if (!q.trim()) {
      setHits([]);
      setViaTranslation(false);
      return;
    }
    setLoading(true);
    debounce.current = setTimeout(async () => {
      const res = await searchIngredients(q);
      setHits(res?.results ?? []);
      setViaTranslation(res?.via_translation ?? false);
      setLoading(false);
    }, 200);
  }, []);

  const onValueChange = (value: string) => {
    setQuery(value);
    runSearch(value);
  };

  const select = (hit: SearchHit) => {
    setOpen(false);
    router.push(`/dashboard/ingredients?highlight=${hit.id}`);
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="overflow-hidden p-0">
        <DialogTitle className="sr-only">Search ingredients</DialogTitle>
        {/* shouldFilter off — the API already ranks results server-side. */}
        <Command shouldFilter={false}>
          <CommandInput
            placeholder="Search ingredients in any language… (jeera, जीरा, cumin)"
            value={query}
            onValueChange={onValueChange}
          />
          <CommandList>
            {viaTranslation && (
              <div className="text-muted-foreground px-3 py-1.5 text-xs">
                matched via translation
              </div>
            )}
            <CommandEmpty>{loading ? "Searching…" : "No ingredients found."}</CommandEmpty>
            <CommandGroup heading="Ingredients">
              {hits.map((hit) => (
                <CommandItem
                  key={hit.id}
                  value={hit.id}
                  onSelect={() => select(hit)}
                  className="flex items-center justify-between gap-3"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{hit.canonical_name_en}</span>
                      {hit.matched_kind === "alias" &&
                        hit.matched_text.toLowerCase() !== hit.canonical_name_en.toLowerCase() && (
                          <span className="text-muted-foreground text-xs">
                            matched “{hit.matched_text}”
                          </span>
                        )}
                      {hit.needs_review && <Badge variant="warning">review</Badge>}
                    </div>
                    {hit.best_price && (
                      <div className="text-muted-foreground mt-0.5 text-xs">
                        {formatBestPrice(hit.best_price)}
                      </div>
                    )}
                  </div>
                  <div className="flex shrink-0 gap-1">
                    <Badge variant="secondary">{hit.category}</Badge>
                    <Badge variant="outline">{hit.purchase_frequency.replace("_", " ")}</Badge>
                  </div>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </DialogContent>
    </Dialog>
  );
}
