import { z } from "zod";

/**
 * Cross-language shared constants and enums for Rasoi Radar.
 *
 * The canonical values live in `packages/shared/schema.json`. This file mirrors
 * them as zod schemas for the web app; `apps/api/app/shared.py` mirrors them as
 * Pydantic for the API. Keep all three in sync.
 */

export * from "./units";

export const APP_NAME = "Rasoi Radar" as const;
export const API_VERSION = "api/v1" as const;

/** Supported UI/user locales (BCP-47 short codes). */
export const localeSchema = z.enum(["en", "hi", "es", "zh", "vi", "ko", "pt"]);
export type Locale = z.infer<typeof localeSchema>;

/** Membership roles within an org (restaurant). */
export const roleSchema = z.enum(["owner", "manager", "staff"]);
export type Role = z.infer<typeof roleSchema>;

/** RFC-7807 problem+json shape returned by the API's exception handler. */
export const problemSchema = z.object({
  type: z.string(),
  title: z.string(),
  status: z.number().int(),
  detail: z.string().optional(),
  instance: z.string().optional(),
});
export type Problem = z.infer<typeof problemSchema>;
