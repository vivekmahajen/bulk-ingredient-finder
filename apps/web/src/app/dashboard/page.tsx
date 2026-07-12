import Link from "next/link";
import { getTranslations } from "next-intl/server";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default async function DashboardHome() {
  const t = await getTranslations("dashboard");
  const tNav = await getTranslations("nav");
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{t("title")}</h1>
        <p className="text-muted-foreground">{t("subtitle")}</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <Link href="/dashboard/ingredients">
          <Card className="hover:border-foreground/30 transition-colors">
            <CardHeader>
              <CardTitle>{tNav("ingredients")}</CardTitle>
              <CardDescription>{t("ingredientsDesc")}</CardDescription>
            </CardHeader>
            <CardContent className="text-muted-foreground text-sm">
              {t("ingredientsHint")}
            </CardContent>
          </Card>
        </Link>
        <Link href="/dashboard/stores">
          <Card className="hover:border-foreground/30 transition-colors">
            <CardHeader>
              <CardTitle>{tNav("stores")}</CardTitle>
              <CardDescription>{t("storesDesc")}</CardDescription>
            </CardHeader>
            <CardContent className="text-muted-foreground text-sm">
              {t("storesHint")}
            </CardContent>
          </Card>
        </Link>
      </div>
    </div>
  );
}
