import { cookies } from "next/headers";
import { getRequestConfig } from "next-intl/server";

/**
 * Locale resolution without URL routing: read the `NEXT_LOCALE` cookie (set by the
 * language switcher, mirrored to `users.locale` via PATCH /me/locale). The app
 * that celebrates multilingual *data* shouldn't be English-only *chrome*.
 */
export const SUPPORTED_LOCALES = ["en", "hi", "es"] as const;
export type AppLocale = (typeof SUPPORTED_LOCALES)[number];
export const DEFAULT_LOCALE: AppLocale = "en";

function coerce(value: string | undefined): AppLocale {
  return SUPPORTED_LOCALES.includes(value as AppLocale) ? (value as AppLocale) : DEFAULT_LOCALE;
}

export default getRequestConfig(async () => {
  const store = await cookies();
  const locale = coerce(store.get("NEXT_LOCALE")?.value);
  const messages = (await import(`../../messages/${locale}.json`)).default;
  return { locale, messages };
});
