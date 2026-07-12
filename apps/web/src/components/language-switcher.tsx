"use client";

import { useTransition } from "react";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { apiPatch } from "@/lib/api";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const LOCALES: ReadonlyArray<{ value: string; label: string }> = [
  { value: "en", label: "English" },
  { value: "hi", label: "हिन्दी" },
  { value: "es", label: "Español" },
];

/**
 * Switches the UI language: sets the NEXT_LOCALE cookie (read by next-intl) and
 * mirrors the choice to the signed-in user's locale via PATCH /me/locale so it
 * persists across devices.
 */
export function LanguageSwitcher() {
  const locale = useLocale();
  const router = useRouter();
  const t = useTranslations("common");
  const [pending, startTransition] = useTransition();

  const change = (next: string) => {
    document.cookie = `NEXT_LOCALE=${next}; path=/; max-age=${60 * 60 * 24 * 365}`;
    // Best-effort persistence to the user record; ignore failure (cookie still applies).
    void apiPatch("/api/v1/me/locale", { locale: next });
    startTransition(() => router.refresh());
  };

  return (
    <Select value={locale} onValueChange={change}>
      <SelectTrigger className="h-8 w-[7.5rem]" aria-label={t("language")} disabled={pending}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {LOCALES.map((l) => (
          <SelectItem key={l.value} value={l.value}>
            {l.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
