import Link from "next/link";
import { useTranslations } from "next-intl";
import { CommandPalette } from "@/components/command-palette";
import { LogPriceDialog } from "@/components/log-price-dialog";
import { LanguageSwitcher } from "@/components/language-switcher";
import { AuthProvider, DashboardGuard } from "@/components/auth-provider";
import { UserMenu } from "@/components/user-menu";
import { Button } from "@/components/ui/button";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const t = useTranslations("nav");
  return (
    <AuthProvider>
      <div className="min-h-screen">
        <header className="border-b">
          <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-4">
            <Link href="/dashboard" className="font-semibold tracking-tight">
              {t("brand")}
            </Link>
            <nav className="text-muted-foreground flex items-center gap-4 text-sm">
              <Link href="/dashboard/ingredients" className="hover:text-foreground">
                {t("ingredients")}
              </Link>
              <Link href="/dashboard/stores" className="hover:text-foreground">
                {t("stores")}
              </Link>
              <Link href="/dashboard/invoices" className="hover:text-foreground">
                {t("invoices")}
              </Link>
              <Link href="/dashboard/compare" className="hover:text-foreground">
                {t("compare")}
              </Link>
              <Link href="/dashboard/prices/bulk" className="hover:text-foreground">
                {t("bulk")}
              </Link>
              <LogPriceDialog
                trigger={
                  <Button size="sm" variant="outline">
                    {t("logPrice")}
                  </Button>
                }
              />
              <LanguageSwitcher />
              <UserMenu />
              <kbd className="bg-muted hidden items-center gap-1 rounded border px-1.5 py-0.5 font-mono text-[10px] sm:inline-flex">
                ⌘K
              </kbd>
            </nav>
          </div>
        </header>
        <div className="mx-auto max-w-5xl px-4 py-8">
          <DashboardGuard>{children}</DashboardGuard>
        </div>
        <CommandPalette />
      </div>
    </AuthProvider>
  );
}
