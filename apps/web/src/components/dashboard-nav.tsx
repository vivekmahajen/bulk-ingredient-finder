"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import { LogPriceDialog } from "@/components/log-price-dialog";
import { LanguageSwitcher } from "@/components/language-switcher";
import { UserMenu } from "@/components/user-menu";
import { Button } from "@/components/ui/button";

const LINKS: ReadonlyArray<readonly [string, string]> = [
  ["/dashboard/ingredients", "ingredients"],
  ["/dashboard/stores", "stores"],
  ["/dashboard/invoices", "invoices"],
  ["/dashboard/compare", "compare"],
  ["/dashboard/prices/bulk", "bulk"],
];

export function DashboardNav() {
  const t = useTranslations("nav");
  const pathname = usePathname();
  const isActive = (href: string) => pathname === href || pathname.startsWith(`${href}/`);

  return (
    <div className="flex items-center gap-2">
      <nav className="hidden items-center gap-1 md:flex">
        {LINKS.map(([href, key]) => (
          <Link
            key={href}
            href={href}
            className={cn(
              "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
              isActive(href)
                ? "bg-accent text-accent-foreground"
                : "text-muted-foreground hover:text-foreground hover:bg-muted",
            )}
          >
            {t(key)}
          </Link>
        ))}
      </nav>
      <div className="bg-border mx-1 hidden h-5 w-px md:block" />
      <LogPriceDialog
        trigger={
          <Button size="sm" variant="outline">
            {t("logPrice")}
          </Button>
        }
      />
      <LanguageSwitcher />
      <UserMenu />
      <kbd className="bg-muted text-muted-foreground hidden items-center gap-1 rounded border px-1.5 py-0.5 font-mono text-[10px] lg:inline-flex">
        ⌘K
      </kbd>
    </div>
  );
}
