"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";

interface Store {
  id: string;
  name: string;
  kind: string;
  city: string | null;
  state: string | null;
  website: string | null;
  delivers: boolean;
}

export default function StoresPage() {
  const [stores, setStores] = useState<Store[] | null>(null);

  useEffect(() => {
    let active = true;
    apiGet<Store[]>("/api/v1/stores").then((res) => {
      if (active && res.ok) setStores(res.data);
    });
    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Stores</h1>
        <p className="text-muted-foreground">
          {stores ? `${stores.length} suppliers` : "Loading…"}
        </p>
      </div>
      <div className="grid gap-3">
        {stores?.map((store) => (
          <Card key={store.id}>
            <CardContent className="flex items-center justify-between gap-4 py-4">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-medium">{store.name}</span>
                  <Badge variant="secondary">{store.kind.replace(/_/g, " ")}</Badge>
                </div>
                <p className="text-muted-foreground mt-1 text-xs">
                  {[store.city, store.state].filter(Boolean).join(", ")}
                  {store.delivers ? " · delivers" : ""}
                </p>
              </div>
              {store.website && (
                <a
                  className="shrink-0 text-sm underline"
                  href={store.website}
                  target="_blank"
                  rel="noreferrer"
                >
                  Website
                </a>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
