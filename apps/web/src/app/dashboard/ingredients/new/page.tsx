"use client"

import { useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "@/components/ui/card"
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { useToast } from "@/components/ui/use-toast"
import { apiPost } from "@/lib/api"
import type {
  Ingredient,
  Category,
  DefaultUnit,
  PurchaseFrequency,
} from "@/lib/types"

/** Languages we surface for `source_lang`, each rendered in its own script. */
const LANGUAGES = [
  { value: "en", label: "English" },
  { value: "hi", label: "हिन्दी" },
  { value: "pa", label: "ਪੰਜਾਬੀ" },
  { value: "gu", label: "ગુજરાતી" },
  { value: "es", label: "Español" },
  { value: "zh", label: "中文" },
  { value: "vi", label: "Tiếng Việt" },
  { value: "ko", label: "한국어" },
  { value: "pt", label: "Português" },
] as const satisfies ReadonlyArray<{ value: string; label: string }>

type LangValue = (typeof LANGUAGES)[number]["value"]

const CATEGORIES = [
  "protein",
  "dairy",
  "produce",
  "staple",
  "spice",
  "frozen",
  "beverage",
  "packaging",
  "other",
] as const satisfies ReadonlyArray<Category>

const DEFAULT_UNITS = [
  "kg",
  "g",
  "l",
  "ml",
  "each",
  "case",
  "bag",
] as const satisfies ReadonlyArray<DefaultUnit>

const PURCHASE_FREQUENCIES = [
  { value: "daily", label: "Daily" },
  { value: "twice_weekly", label: "2×/week" },
  { value: "weekly", label: "Weekly" },
  { value: "biweekly", label: "Biweekly" },
  { value: "monthly", label: "Monthly" },
  { value: "quarterly", label: "Quarterly" },
] as const satisfies ReadonlyArray<{ value: PurchaseFrequency; label: string }>

function langLabel(value: string): string {
  return LANGUAGES.find((l) => l.value === value)?.label ?? value
}

interface CreateIngredientBody {
  display_name: string
  source_lang: string
  category: Category
  default_unit: DefaultUnit
  purchase_frequency: PurchaseFrequency
  par_level?: number
}

export default function NewIngredientPage() {
  const router = useRouter()
  const { toast } = useToast()

  // Controlled form state.
  const [displayName, setDisplayName] = useState<string>("")
  const [sourceLang, setSourceLang] = useState<LangValue>("en")
  const [category, setCategory] = useState<Category>("produce")
  const [defaultUnit, setDefaultUnit] = useState<DefaultUnit>("kg")
  const [purchaseFrequency, setPurchaseFrequency] =
    useState<PurchaseFrequency>("weekly")
  const [parLevel, setParLevel] = useState<string>("")

  const [submitting, setSubmitting] = useState<boolean>(false)
  const [created, setCreated] = useState<Ingredient | null>(null)
  const [langChoices, setLangChoices] = useState<string | null>(null)

  async function submit(langOverride?: LangValue): Promise<void> {
    const trimmed = displayName.trim()
    if (!trimmed) {
      toast({
        title: "Name required",
        description: "Enter a name for the ingredient.",
        variant: "destructive",
      })
      return
    }

    const lang = langOverride ?? sourceLang
    const body: CreateIngredientBody = {
      display_name: trimmed,
      source_lang: lang,
      category,
      default_unit: defaultUnit,
      purchase_frequency: purchaseFrequency,
    }
    if (parLevel.trim() !== "") {
      const n = Number(parLevel)
      if (!Number.isNaN(n)) {
        body.par_level = n
      }
    }

    setSubmitting(true)
    const result = await apiPost<Ingredient>("/api/v1/ingredients", body)
    setSubmitting(false)

    if (result.ok) {
      const ing = result.data
      setCreated(ing)
      setLangChoices(null)
      toast({ title: `Added ${ing.canonical_name_en}` })
      // Reset for quick repeated entry; stay on-page.
      setDisplayName("")
      setSourceLang("en")
      setParLevel("")
      return
    }

    // Language ambiguity → inline chooser that re-submits on pick.
    if (
      result.status === 422 &&
      result.problem.title === "Ambiguous language"
    ) {
      setLangChoices(
        result.problem.detail ?? "Pick the language this name is written in."
      )
      return
    }

    setLangChoices(null)
    toast({
      title: result.problem.title,
      description: result.problem.detail,
      variant: "destructive",
    })
  }

  function onSubmit(e: React.FormEvent<HTMLFormElement>): void {
    e.preventDefault()
    void submit()
  }

  function chooseLang(value: LangValue): void {
    setSourceLang(value)
    void submit(value)
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6">
      <div className="space-y-1">
        <Link
          href="/dashboard/ingredients"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          ← All ingredients
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight">
          Add Ingredient
        </h1>
      </div>

      <Card>
        <form onSubmit={onSubmit}>
          <CardHeader>
            <CardTitle>New ingredient</CardTitle>
            <CardDescription>
              Type the name in any language — we&apos;ll canonicalize it and
              keep the original as a searchable alias.
            </CardDescription>
          </CardHeader>

          <CardContent className="space-y-6">
            {/* Display name + language */}
            <div className="space-y-2">
              <label
                htmlFor="display_name"
                className="text-sm font-medium leading-none"
              >
                Name
              </label>
              <div className="flex gap-2">
                <Input
                  id="display_name"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="e.g. हल्दी, cilantro, 두부"
                  autoComplete="off"
                  className="flex-1"
                />
                <Select
                  value={sourceLang}
                  onValueChange={(v) => setSourceLang(v as LangValue)}
                >
                  <SelectTrigger className="w-[140px]" aria-label="Language">
                    <SelectValue placeholder="Language" />
                  </SelectTrigger>
                  <SelectContent>
                    {LANGUAGES.map((l) => (
                      <SelectItem key={l.value} value={l.value}>
                        {l.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Category + default unit */}
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <label className="text-sm font-medium leading-none">
                  Category
                </label>
                <Select
                  value={category}
                  onValueChange={(v) => setCategory(v as Category)}
                >
                  <SelectTrigger aria-label="Category">
                    <SelectValue placeholder="Category" />
                  </SelectTrigger>
                  <SelectContent>
                    {CATEGORIES.map((c) => (
                      <SelectItem key={c} value={c} className="capitalize">
                        {c}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium leading-none">
                  Default unit
                </label>
                <Select
                  value={defaultUnit}
                  onValueChange={(v) => setDefaultUnit(v as DefaultUnit)}
                >
                  <SelectTrigger aria-label="Default unit">
                    <SelectValue placeholder="Unit" />
                  </SelectTrigger>
                  <SelectContent>
                    {DEFAULT_UNITS.map((u) => (
                      <SelectItem key={u} value={u}>
                        {u}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Purchase frequency — radio-style toggle buttons */}
            <div className="space-y-2">
              <span className="text-sm font-medium leading-none">
                Purchase frequency
              </span>
              <div className="flex flex-wrap gap-2" role="radiogroup">
                {PURCHASE_FREQUENCIES.map((f) => {
                  const selected = purchaseFrequency === f.value
                  return (
                    <Button
                      key={f.value}
                      type="button"
                      size="sm"
                      role="radio"
                      aria-checked={selected}
                      variant={selected ? "default" : "outline"}
                      onClick={() => setPurchaseFrequency(f.value)}
                    >
                      {f.label}
                    </Button>
                  )
                })}
              </div>
            </div>

            {/* Par level */}
            <div className="space-y-2">
              <label
                htmlFor="par_level"
                className="text-sm font-medium leading-none"
              >
                Par level{" "}
                <span className="font-normal text-muted-foreground">
                  (optional)
                </span>
              </label>
              <Input
                id="par_level"
                type="number"
                inputMode="decimal"
                min={0}
                step="any"
                value={parLevel}
                onChange={(e) => setParLevel(e.target.value)}
                placeholder="e.g. 5"
                className="max-w-[160px]"
              />
            </div>

            {/* Inline language ambiguity chooser */}
            {langChoices !== null && (
              <div className="space-y-2 rounded-md border border-amber-300 bg-amber-50 p-3 dark:border-amber-800 dark:bg-amber-950/40">
                <p className="text-sm font-medium">Which language is this?</p>
                {langChoices ? (
                  <p className="text-sm text-muted-foreground">{langChoices}</p>
                ) : null}
                <div className="flex flex-wrap gap-2 pt-1">
                  {LANGUAGES.map((l) => (
                    <Button
                      key={l.value}
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={submitting}
                      onClick={() => chooseLang(l.value)}
                    >
                      {l.label}
                    </Button>
                  ))}
                </div>
              </div>
            )}
          </CardContent>

          <CardFooter className="flex items-center justify-between gap-3">
            <Button type="submit" disabled={submitting}>
              {submitting ? "Adding…" : "Add ingredient"}
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={() => router.push("/dashboard/ingredients")}
            >
              Done
            </Button>
          </CardFooter>
        </form>
      </Card>

      {/* Live / result preview */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Preview</CardTitle>
          <CardDescription>
            {created
              ? "Saved. Add another above to keep going."
              : "Updates as you type."}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          {created ? (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">
                  Will be saved as: {created.canonical_name_en}
                </span>
                {created.needs_review ? (
                  <Badge variant="warning">Needs review</Badge>
                ) : null}
              </div>
              {created.aliases.length > 0 ? (
                <p className="text-muted-foreground">
                  also findable as:{" "}
                  {created.aliases.map((a) => a.alias).join(", ")}
                </p>
              ) : (
                <p className="text-muted-foreground">No aliases recorded.</p>
              )}
            </>
          ) : displayName.trim() ? (
            <>
              <p className="font-medium">
                Will be saved as: {displayName.trim()}
              </p>
              <p className="text-muted-foreground">
                language: {langLabel(sourceLang)}
              </p>
            </>
          ) : (
            <p className="text-muted-foreground">
              Start typing a name to see the preview.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
