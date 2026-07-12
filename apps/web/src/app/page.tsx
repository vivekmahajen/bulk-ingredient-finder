import { redirect } from "next/navigation";

/**
 * The app has no public marketing surface — the landing route sends visitors
 * straight into the dashboard. `middleware.ts` guards `/dashboard/**`, so an
 * unauthenticated visitor is bounced on to `/login` (preserving `?next`),
 * which is the entry point to the auth module.
 */
export default function Home() {
  redirect("/dashboard");
}
