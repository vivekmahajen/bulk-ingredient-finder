"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import zxcvbn from "zxcvbn";
import { Camera, Check } from "lucide-react";

import { Logo, LogoMark } from "@/components/brand";
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
import { register, LOCALE_OPTIONS } from "@/lib/auth";

const STRENGTH_LABELS: readonly string[] = ["Weak", "Weak", "Fair", "Good", "Strong"];
const STRENGTH_COLORS: readonly string[] = [
  "bg-destructive",
  "bg-destructive",
  "bg-amber-500",
  "bg-emerald-500",
  "bg-emerald-600",
];

const EMAIL_RE = new RegExp("^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$");

export default function RegisterPage(): React.JSX.Element {
  const router = useRouter();
  const { toast } = useToast();

  const [orgName, setOrgName] = React.useState<string>("");
  const [displayName, setDisplayName] = React.useState<string>("");
  const [email, setEmail] = React.useState<string>("");
  const [password, setPassword] = React.useState<string>("");
  const [locale, setLocale] = React.useState<string>("en");
  const [error, setError] = React.useState<string | null>(null);
  const [disabled, setDisabled] = React.useState<boolean>(false);
  const [submitting, setSubmitting] = React.useState<boolean>(false);

  const score = React.useMemo<number>(
    () => (password.length > 0 ? zxcvbn(password).score : 0),
    [password],
  );

  const policyMet = password.length >= 10 && score >= 3;
  const canSubmit =
    policyMet &&
    orgName.trim().length > 0 &&
    displayName.trim().length > 0 &&
    EMAIL_RE.test(email) &&
    !submitting;

  const onSubmit = async (e: React.FormEvent<HTMLFormElement>): Promise<void> => {
    e.preventDefault();
    setError(null);
    if (!canSubmit) {
      if (!EMAIL_RE.test(email)) {
        setError("Please enter a valid email address.");
      }
      return;
    }

    setSubmitting(true);
    try {
      const result = await register({
        org_name: orgName.trim(),
        email: email.trim(),
        password,
        display_name: displayName.trim(),
        locale,
      });
      if (result.ok) {
        router.push("/dashboard");
        return;
      }
      // 403 = self-registration is off in single-restaurant (dogfood) mode.
      if (result.status === 403) {
        setDisabled(true);
        setError(null);
        return;
      }
      const message = result.detail ?? result.title ?? "Could not create your account.";
      setError(message);
      toast({
        variant: "destructive",
        title: result.title ?? "Registration failed",
        description: result.detail,
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      {/* Brand panel */}
      <aside className="bg-brand-gradient relative hidden flex-col justify-between overflow-hidden p-10 text-white lg:flex">
        <div className="grid-fade pointer-events-none absolute inset-0 opacity-10" />
        <Link href="/" className="relative">
          <Logo textClassName="text-white" />
        </Link>
        <div className="relative">
          <h2 className="max-w-md text-3xl font-bold leading-tight tracking-tight">
            Set up your kitchen in a minute.
          </h2>
          <ul className="mt-8 space-y-3 text-teal-50">
            {[
              "Photograph invoices in any language",
              "Compare true $/kg across suppliers",
              "Free to start — no card required",
            ].map((t) => (
              <li key={t} className="flex items-center gap-3">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-white/15">
                  <Check className="h-3.5 w-3.5" />
                </span>
                <span className="text-sm font-medium">{t}</span>
              </li>
            ))}
          </ul>
        </div>
        <p className="relative flex items-center gap-2 text-sm text-teal-100/80">
          <Camera className="h-4 w-4" /> Snap · review · commit — nothing counts until you confirm.
        </p>
      </aside>

      {/* Form */}
      <div className="flex min-h-screen items-center justify-center p-4">
        <Card className="w-full max-w-sm border-none shadow-none sm:border sm:shadow-sm">
          <CardHeader className="space-y-1">
            <Link href="/" className="mb-1 inline-flex lg:hidden">
              <LogoMark />
            </Link>
            <CardTitle className="text-2xl">Create your account</CardTitle>
            <CardDescription>Set up your kitchen on Rasoi Radar.</CardDescription>
          </CardHeader>
          <CardContent>
          {disabled ? (
            <div className="space-y-4">
              <p className="text-sm">
                Self-registration is turned off for this deployment — accounts are added by
                invitation. Ask an administrator to invite you, then use the link they send.
              </p>
              <Button asChild variant="outline" className="w-full">
                <Link href="/login">Back to sign in</Link>
              </Button>
            </div>
          ) : (
            <form onSubmit={onSubmit} className="space-y-4" noValidate>
              <div className="space-y-1">
                <label htmlFor="org_name" className="text-sm font-medium">
                  Restaurant / kitchen name
                </label>
                <Input
                  id="org_name"
                  autoComplete="organization"
                  value={orgName}
                  onChange={(e) => setOrgName(e.target.value)}
                />
              </div>

              <div className="space-y-1">
                <label htmlFor="display_name" className="text-sm font-medium">
                  Your name
                </label>
                <Input
                  id="display_name"
                  autoComplete="name"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                />
              </div>

              <div className="space-y-1">
                <label htmlFor="email" className="text-sm font-medium">
                  Email
                </label>
                <Input
                  id="email"
                  type="email"
                  autoComplete="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
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
                {submitting ? "Creating account…" : "Create account"}
              </Button>

              <div className="text-muted-foreground text-center text-sm">
                Already have an account?{" "}
                <Link href="/login" className="underline-offset-4 hover:underline">
                  Sign in
                </Link>
              </div>
            </form>
          )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
