import Link from "next/link";
import { CommandPalette } from "@/components/command-palette";
import { DashboardNav } from "@/components/dashboard-nav";
import { AuthProvider, DashboardGuard } from "@/components/auth-provider";
import { Logo } from "@/components/brand";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <div className="bg-muted/30 min-h-screen">
        <header className="border-border/70 bg-background/85 sticky top-0 z-40 border-b backdrop-blur">
          <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
            <Link href="/dashboard" className="shrink-0">
              <Logo />
            </Link>
            <DashboardNav />
          </div>
        </header>
        <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
          <DashboardGuard>{children}</DashboardGuard>
        </div>
        <CommandPalette />
      </div>
    </AuthProvider>
  );
}
