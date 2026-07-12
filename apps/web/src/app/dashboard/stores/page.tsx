"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { apiGet } from "@/lib/api";
import { type Store } from "@/lib/stores";
import { useEnumLabels } from "@/lib/i18n-labels";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { StoreFormDialog } from "@/components/store-form-dialog";

export default function StoresPage() {
  const t = useTranslations("stores");
  const labels = useEnumLabels();
  const [stores, setStores] = useState<Store[] | null>(null);

  const load = useCallback(() => {
    apiGet<Store[]>("/api/v1/stores").then((res) => {
      if (res.ok) setStores(res.data);
    });
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{t("title")}</h1>
          <p className="text-muted-foreground">
            {stores ? `${stores.length} ${t("suppliers")}` : t("loading")}
          </p>
        </div>
        <StoreFormDialog onSaved={load} trigger={<Button>＋ {t("add")}</Button>} />
      </div>

      <div className="grid gap-3">
        {stores?.map((store) => (
          <Card key={store.id} className="hover:border-foreground/30 transition-colors">
            <CardContent className="flex items-center justify-between gap-4 py-4">
              <Link href={`/dashboard/stores/${store.id}`} className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{store.name}</span>
                  <Badge variant="secondary">{labels.storeKind(store.kind)}</Badge>
                  {!store.geocoded && <Badge variant="warning">{t("noLocation")}</Badge>}
                </div>
                <p className="text-muted-foreground mt-1 text-xs">
                  {[store.city, store.state].filter(Boolean).join(", ")}
                  {store.delivers && store.delivery_days?.length
                    ? ` · ${t("delivers")} ${store.delivery_days.join(", ")}`
                    : store.delivers
                      ? ` · ${t("delivers")}`
                      : ""}
                  {store.min_order ? ` · ${t("minOrder", { amount: store.min_order })}` : ""}
                </p>
              </Link>
              <div className="flex shrink-0 items-center gap-3">
                {store.distance_km != null && (
                  <span className="text-muted-foreground text-sm">
                    {t("kmValue", { km: store.distance_km.toFixed(0) })}
                  </span>
                )}
                {store.website && (
                  <a
                    className="text-sm underline"
                    href={store.website}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {t("website")}
                  </a>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {stores?.length === 0 && (
        <p className="text-muted-foreground text-sm">{t("empty")}</p>
      )}
    </div>
  );
}
