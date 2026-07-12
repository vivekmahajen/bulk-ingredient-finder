"use client";

import * as React from "react";
import { useParams, useRouter } from "next/navigation";
import zxcvbn from "zxcvbn";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/components/ui/use-toast";
import { acceptInvite, LOCALE_OPTIONS } from "@/lib/auth";

const STRENGTH_LABELS: readonly string[] = ["Weak", "Weak", "Fair", "Good", "Strong"];
const STRENGTH_COLORS: readonly string[] = [
  "bg-destructive",
  "bg-destructive",
  "bg-amber-500",
  "bg-emerald-500",
  "bg-emerald-600",
];

export default function AcceptInvitePage(): React.JSX.Element {
  const params = useParams<{ token: string }>();
  const token = params.token;
  const router = useRouter();
  const { toast } = useToast();

  const [displayName, setDisplayName] = React.useState<string>("");
  const [password, setPassword] = React.useState<string>("");
  const [locale, setLocale] = React.useState<string>("en");
  const [error, setError] = React.useState<string | null>(null);
  const [submitting, setSubmitting] = React.useState<boolean>(false);

  const score = React.useMemo<number>(
    () => (password.length > 0 ? zxcvbn(password).score : 0),
    [password],
  );

  const policyMet = password.length >= 10 && score >= 3;
  const canSubmit = policyMet && displayName.trim().length > 0 && !submitting;

  const onSubmit = async (e: React.FormEvent<HTMLFormElement>): Promise<void> => {
    e.preventDefault();
    setError(null);
    if (!policyMet || displayName.trim().length === 0) {
      return;
    }

    setSubmitting(true);
    try {
      const result = await acceptInvite({
        token,
        password,
        display_name: displayName.trim(),
        locale,
      });
      if (result.ok) {
        router.push("/dashboard");
        return;
      }
      const message = result.detail ?? result.title ?? "This invite is invalid or has expired.";
      setError(message);
      toast({
        variant: "destructive",
        title: result.title ?? "Could not accept invite",
        description: result.detail,
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="grid min-h-screen place-items-center p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Accept your invite</CardTitle>
          <CardDescription>Set up your Rasoi Radar account</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-4" noValidate>
            <div className="space-y-1">
              <label htmlFor="display_name" className="text-sm font-medium">
                Display name
              </label>
              <Input
                id="display_name"
                autoComplete="name"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
              />
            </div>

            <div className="space-y-1">
              <label htmlFor="password" className="text-sm font-medium">
                Password
              </label>
              <Input
                id="password"
                type="password"
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <div className="flex items-center gap-2 pt-1">
                <div className="bg-muted h-1.5 flex-1 overflow-hidden rounded-full">
                  <div
                    className={`h-full transition-all ${STRENGTH_COLORS[score]}`}
                    style={{ width: `${((score + 1) / 5) * 100}%` }}
                  />
                </div>
                <span className="text-muted-foreground w-12 text-right text-xs">
                  {password.length > 0 ? STRENGTH_LABELS[score] : ""}
                </span>
              </div>
              <p className="text-muted-foreground text-xs">
                ≥10 characters, strength Good or better
              </p>
            </div>

            <div className="space-y-1">
              <label htmlFor="locale" className="text-sm font-medium">
                Preferred language
              </label>
              <Select value={locale} onValueChange={setLocale}>
                <SelectTrigger id="locale">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {LOCALE_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {error !== null ? (
              <p className="text-destructive text-sm" role="alert">
                {error}
              </p>
            ) : null}

            <Button type="submit" className="w-full" disabled={!canSubmit}>
              {submitting ? "Setting up…" : "Accept invite"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
