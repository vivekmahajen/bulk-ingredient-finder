import { apiGet, apiPost } from "@/lib/api";

export type Role = "owner" | "manager" | "staff";

export interface Me {
  id: string;
  email: string;
  display_name: string;
  locale: string;
  role: Role;
  org: { id: string; name: string };
}

export async function fetchMe(): Promise<Me | null> {
  const res = await apiGet<Me>("/api/v1/me");
  return res.ok ? res.data : null;
}

export interface AuthResult {
  ok: boolean;
  title?: string;
  detail?: string;
  status?: number;
}

export async function login(email: string, password: string): Promise<AuthResult> {
  const res = await apiPost<{ ok: boolean }>("/api/v1/auth/login", { email, password });
  return res.ok
    ? { ok: true }
    : { ok: false, title: res.problem.title, detail: res.problem.detail, status: res.status };
}

export async function requestMagicLink(email: string): Promise<AuthResult> {
  const res = await apiPost<{ ok: boolean }>("/api/v1/auth/magic-link", { email });
  return res.ok
    ? { ok: true }
    : { ok: false, title: res.problem.title, detail: res.problem.detail };
}

export async function logout(): Promise<void> {
  await apiPost("/api/v1/auth/logout", {});
}

export async function acceptInvite(input: {
  token: string;
  password: string;
  display_name: string;
  locale: string;
}): Promise<AuthResult> {
  const res = await apiPost<{ ok: boolean }>("/api/v1/auth/invites/accept", input);
  return res.ok
    ? { ok: true }
    : { ok: false, title: res.problem.title, detail: res.problem.detail };
}

/** BCP-47 locale options for signup/invite, each rendered in its own script. */
export const LOCALE_OPTIONS: ReadonlyArray<{ value: string; label: string }> = [
  { value: "en", label: "English" },
  { value: "hi", label: "हिन्दी" },
  { value: "es", label: "Español" },
  { value: "zh", label: "中文" },
  { value: "vi", label: "Tiếng Việt" },
  { value: "ko", label: "한국어" },
  { value: "pt", label: "Português" },
];
