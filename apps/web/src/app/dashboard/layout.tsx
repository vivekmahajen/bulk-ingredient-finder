import Link from "next/link";
import { useTranslations } from "next-intl";
import { CommandPalette } from "@/components/command-palette";
import { LogPriceDialog } from "@/components/log-price-dialog";
import { LanguageSwitcher } from "@/components/language-switcher";
import { Button } from "@/components/ui/button";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const t = useTranslations("nav");
  return (
    <div className="min-h-screen">
      <header className="border-b">
        <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-4">
          <Link href="/dashboard" className="font-semibold tracking-tight">
            {t("brand")}
          </Link>
          <nav className="flex items-center gap-4 text-sm text-muted-foreground">
            <Link href="/dashboard/ingredients" className="hover:text-foreground">
              {t("ingredients")}
            </Link>
            <Link href="/dashboard/stores" className="hover:text-foreground">
              {t("stores")}
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
            <kbd className="hidden items-center gap-1 rounded border bg-muted px-1.5 py-0.5 font-mono text-[10px] sm:inline-flex">
              ⌘K
            </kbd>
          </nav>
        </div>
      </header>
      <div className="mx-auto max-w-5xl px-4 py-8">{children}</div>
      <CommandPalette />
    </div>
  );
}
