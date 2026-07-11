"use client";

import { useState } from "react";
import { apiPost, apiPatch } from "@/lib/api";
import { DELIVERY_DAYS, STORE_KINDS, type Store, type StoreKind } from "@/lib/stores";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/components/ui/use-toast";

interface StoreFormDialogProps {
  store?: Store;
  onSaved: (s: Store) => void;
  trigger: React.ReactNode;
}

/** Payload sent to POST/PATCH — empty values omitted so the API keeps them null. */
interface StorePayload {
  name: string;
  kind: StoreKind;
  address_line?: string;
  city?: string;
  state?: string;
  postal?: string;
  website?: string;
  phone?: string;
  delivers: boolean;
  delivery_days?: string[];
  min_order?: number;
  notes?: string;
  lat?: number;
  lng?: number;
}

function trimmedOrUndefined(value: string): string | undefined {
  const t = value.trim();
  return t.length > 0 ? t : undefined;
}

function numberOrUndefined(value: string): number | undefined {
  const t = value.trim();
  if (t.length === 0) return undefined;
  const n = Number(t);
  return Number.isFinite(n) ? n : undefined;
}

export function StoreFormDialog({ store, onSaved, trigger }: StoreFormDialogProps) {
  const { toast } = useToast();
  const isEdit = store !== undefined;

  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [geocodeWarning, setGeocodeWarning] = useState(false);

  const [name, setName] = useState(store?.name ?? "");
  const [kind, setKind] = useState<StoreKind>(store?.kind ?? "broadline");
  const [addressLine, setAddressLine] = useState(store?.address_line ?? "");
  const [city, setCity] = useState(store?.city ?? "");
  const [stateField, setStateField] = useState(store?.state ?? "");
  const [postal, setPostal] = useState(store?.postal ?? "");
  const [website, setWebsite] = useState(store?.website ?? "");
  const [phone, setPhone] = useState(store?.phone ?? "");
  const [delivers, setDelivers] = useState(store?.delivers ?? false);
  const [deliveryDays, setDeliveryDays] = useState<string[]>(store?.delivery_days ?? []);
  const [minOrder, setMinOrder] = useState(store?.min_order != null ? String(store.min_order) : "");
  const [notes, setNotes] = useState(store?.notes ?? "");
  const [lat, setLat] = useState(store?.lat != null ? String(store.lat) : "");
  const [lng, setLng] = useState(store?.lng != null ? String(store.lng) : "");

  function toggleDay(day: string) {
    setDeliveryDays((prev) =>
      prev.includes(day) ? prev.filter((d) => d !== day) : [...prev, day],
    );
  }

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (name.trim().length === 0) {
      toast({
        title: "Name required",
        description: "Give the store a name before saving.",
        variant: "destructive",
      });
      return;
    }

    const payload: StorePayload = {
      name: name.trim(),
      kind,
      address_line: trimmedOrUndefined(addressLine),
      city: trimmedOrUndefined(city),
      state: trimmedOrUndefined(stateField),
      postal: trimmedOrUndefined(postal),
      website: trimmedOrUndefined(website),
      phone: trimmedOrUndefined(phone),
      delivers,
      delivery_days: delivers && deliveryDays.length > 0 ? deliveryDays : undefined,
      min_order: numberOrUndefined(minOrder),
      notes: trimmedOrUndefined(notes),
      lat: numberOrUndefined(lat),
      lng: numberOrUndefined(lng),
    };

    setSubmitting(true);
    setGeocodeWarning(false);
    const result = isEdit
      ? await apiPatch<Store>(`/api/v1/stores/${store.id}`, payload)
      : await apiPost<Store>("/api/v1/stores", payload);
    setSubmitting(false);

    if (!result.ok) {
      toast({
        title: result.problem.title,
        description: result.problem.detail,
        variant: "destructive",
      });
      return;
    }

    if (result.data.geocoded === false) {
      setGeocodeWarning(true);
      onSaved(result.data);
      toast({
        title: "Saved, but no location",
        description: "We couldn't pin this address — add latitude/longitude manually.",
      });
      // Keep the dialog open so the user can enter coordinates.
      return;
    }

    toast({
      title: isEdit ? "Store updated" : "Store added",
      description: `${result.data.name} saved.`,
    });
    onSaved(result.data);
    setOpen(false);
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit store" : "Add store"}</DialogTitle>
          <DialogDescription>
            {isEdit ? "Update this supplier's details." : "Add a supplier to track its prices."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1">
            <label htmlFor="store-name" className="text-sm font-medium">
              Name
            </label>
            <Input
              id="store-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="CHEF'STORE Redding"
              required
            />
          </div>

          <div className="space-y-1">
            <label className="text-sm font-medium">Kind</label>
            <Select value={kind} onValueChange={(v) => setKind(v as StoreKind)}>
              <SelectTrigger>
                <SelectValue placeholder="Select kind" />
              </SelectTrigger>
              <SelectContent>
                {STORE_KINDS.map((k) => (
                  <SelectItem key={k.value} value={k.value}>
                    {k.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1">
            <label htmlFor="store-address" className="text-sm font-medium">
              Address
            </label>
            <Input
              id="store-address"
              value={addressLine}
              onChange={(e) => setAddressLine(e.target.value)}
              placeholder="123 Market St"
            />
          </div>

          <div className="grid grid-cols-3 gap-2">
            <div className="space-y-1">
              <label htmlFor="store-city" className="text-sm font-medium">
                City
              </label>
              <Input id="store-city" value={city} onChange={(e) => setCity(e.target.value)} />
            </div>
            <div className="space-y-1">
              <label htmlFor="store-state" className="text-sm font-medium">
                State
              </label>
              <Input
                id="store-state"
                value={stateField}
                onChange={(e) => setStateField(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <label htmlFor="store-postal" className="text-sm font-medium">
                Postal
              </label>
              <Input id="store-postal" value={postal} onChange={(e) => setPostal(e.target.value)} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1">
              <label htmlFor="store-website" className="text-sm font-medium">
                Website
              </label>
              <Input
                id="store-website"
                value={website}
                onChange={(e) => setWebsite(e.target.value)}
                placeholder="https://…"
              />
            </div>
            <div className="space-y-1">
              <label htmlFor="store-phone" className="text-sm font-medium">
                Phone
              </label>
              <Input id="store-phone" value={phone} onChange={(e) => setPhone(e.target.value)} />
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium">Delivers</span>
              <Button
                type="button"
                size="sm"
                variant={delivers ? "default" : "outline"}
                onClick={() => setDelivers((d) => !d)}
              >
                {delivers ? "Yes" : "No"}
              </Button>
            </div>
            {delivers && (
              <div className="flex flex-wrap gap-2">
                {DELIVERY_DAYS.map((day) => (
                  <Button
                    key={day}
                    type="button"
                    size="sm"
                    variant={deliveryDays.includes(day) ? "default" : "outline"}
                    onClick={() => toggleDay(day)}
                  >
                    {day}
                  </Button>
                ))}
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1">
              <label htmlFor="store-min-order" className="text-sm font-medium">
                Min order ($)
              </label>
              <Input
                id="store-min-order"
                type="number"
                inputMode="decimal"
                value={minOrder}
                onChange={(e) => setMinOrder(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <label htmlFor="store-notes" className="text-sm font-medium">
                Notes
              </label>
              <Input id="store-notes" value={notes} onChange={(e) => setNotes(e.target.value)} />
            </div>
          </div>

          <div className="space-y-2 rounded-md border border-dashed p-3">
            <p className="text-muted-foreground text-xs">
              Coordinates (optional — set automatically from the address)
            </p>
            {geocodeWarning && (
              <p className="rounded-md bg-amber-100 px-3 py-2 text-sm text-amber-900 dark:bg-amber-900/40 dark:text-amber-200">
                We couldn&apos;t pin this address — add latitude/longitude manually.
              </p>
            )}
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <label htmlFor="store-lat" className="text-sm font-medium">
                  Latitude
                </label>
                <Input
                  id="store-lat"
                  type="number"
                  inputMode="decimal"
                  value={lat}
                  onChange={(e) => setLat(e.target.value)}
                />
              </div>
              <div className="space-y-1">
                <label htmlFor="store-lng" className="text-sm font-medium">
                  Longitude
                </label>
                <Input
                  id="store-lng"
                  type="number"
                  inputMode="decimal"
                  value={lng}
                  onChange={(e) => setLng(e.target.value)}
                />
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? "Saving…" : isEdit ? "Save changes" : "Add store"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
