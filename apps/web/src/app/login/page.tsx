"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Camera, Languages, MapPin } from "lucide-react";

import { Logo, LogoMark } from "@/components/brand";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/use-toast";
import { login, requestMagicLink } from "@/lib/auth";

type Mode = "password" | "magic";

const EMAIL_RE = new RegExp("^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$");

export default function LoginPage(): React.JSX.Element {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { toast } = useToast();

  const next = searchParams.get("next") ?? "/dashboard";

  const [mode, setMode] = React.useState<Mode>("password");
  const [email, setEmail] = React.useState<string>("");
  const [password, setPassword] = React.useState<string>("");
  const [error, setError] = React.useState<string | null>(null);
  const [locked, setLocked] = React.useState<boolean>(false);
  const [submitting, setSubmitting] = React.useState<boolean>(false);
  const [magicSent, setMagicSent] = React.useState<boolean>(false);

  const switchMode = (nextMode: Mode): void => {
    setMode(nextMode);
    setError(null);
    setLocked(false);
    setMagicSent(false);
  };

  const onPasswordSubmit = async (e: React.FormEvent<HTMLFormElement>): Promise<void> => {
    e.preventDefault();
    setError(null);
    setLocked(false);

    if (!EMAIL_RE.test(email)) {
      setError("Please enter a valid email address.");
      return;
    }
    if (password.length === 0) {
      setError("Please enter your password.");
      return;
    }

    setSubmitting(true);
    try {
      const result = await login(email, password);
      if (result.ok) {
        router.push(next);
        return;
      }
      const message = result.detail ?? result.title ?? "Unable to sign in.";
      setError(message);
      if (result.status === 403) {
        setLocked(true);
      }
      toast({
        variant: "destructive",
        title: result.title ?? "Sign in failed",
        description: result.detail,
      });
    } finally {
      setSubmitting(false);
    }
  };

  const onMagicSubmit = async (e: React.FormEvent<HTMLFormElement>): Promise<void> => {
    e.preventDefault();
    setError(null);

    if (!EMAIL_RE.test(email)) {
      setError("Please enter a valid email address.");
      return;
    }

    setSubmitting(true);
    try {
      await requestMagicLink(email);
      setMagicSent(true);
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
            The invoices legacy OCR can&apos;t read, finally turned into prices.
          </h2>
          <ul className="mt-8 space-y-3 text-teal-50">
            {[
              [Camera, "Photograph any invoice — any language"],
              [Languages, "हल्दी · jeera · cumin — one catalog"],
              [MapPin, "Cheapest supplier within your radius"],
            ].map(([Icon, label], i) => (
              <li key={i} className="flex items-center gap-3">
                <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/15">
                  <Icon className="h-4 w-4" />
                </span>
                <span className="text-sm font-medium">{label as string}</span>
              </li>
            ))}
          </ul>
        </div>
        <p className="relative text-sm text-teal-100/80">
          Extraction proposes — humans commit. Nothing enters your price map unreviewed.
        </p>
      </aside>

      {/* Form */}
      <div className="flex min-h-screen items-center justify-center p-4">
        <Card className="w-full max-w-sm border-none shadow-none sm:border sm:shadow-sm">
          <CardHeader className="space-y-1">
            <Link href="/" className="mb-1 inline-flex lg:hidden">
              <LogoMark />
            </Link>
            <CardTitle className="text-2xl">Welcome back</CardTitle>
            <CardDescription>Sign in to your kitchen&apos;s dashboard.</CardDescription>
          </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-2">
            <Button
              type="button"
              variant={mode === "password" ? "default" : "outline"}
              onClick={() => switchMode("password")}
            >
              Password
            </Button>
            <Button
              type="button"
              variant={mode === "magic" ? "default" : "outline"}
              onClick={() => switchMode("magic")}
            >
              Magic link
            </Button>
          </div>

          {mode === "password" ? (
            <form onSubmit={onPasswordSubmit} className="space-y-3" noValidate>
              <Input
                type="email"
                autoComplete="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                aria-label="Email"
              />
              <Input
                type="password"
                autoComplete="current-password"
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                aria-label="Password"
              />
              {error !== null ? (
                <p className="text-destructive text-sm" role="alert">
                  {error}
                </p>
              ) : null}
              {locked ? (
                <p className="text-sm text-amber-600 dark:text-amber-400">
                  This account appears to be locked. Please contact your administrator.
                </p>
              ) : null}
              <Button type="submit" className="w-full" disabled={submitting}>
                {submitting ? "Signing in…" : "Sign in"}
              </Button>
              <div className="text-center text-sm">
                <Link
                  href="/login?forgot=1"
                  className="text-muted-foreground underline-offset-4 hover:underline"
                >
                  Forgot password?
                </Link>
              </div>
              {searchParams.get("forgot") === "1" ? (
                <p className="text-muted-foreground text-center text-xs">
                  Use the magic link tab to receive a sign-in link by email.
                </p>
              ) : null}
            </form>
          ) : (
            <form onSubmit={onMagicSubmit} className="space-y-3" noValidate>
              <Input
                type="email"
                autoComplete="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                aria-label="Email"
              />
              {error !== null ? (
                <p className="text-destructive text-sm" role="alert">
                  {error}
                </p>
              ) : null}
              {magicSent ? (
                <p className="text-muted-foreground text-sm">
                  If that email exists, a sign-in link is on its way.
                </p>
              ) : null}
              <Button type="submit" className="w-full" disabled={submitting}>
                {submitting ? "Sending…" : "Send magic link"}
              </Button>
            </form>
          )}

          <div className="border-t pt-4 text-center text-sm">
            <span className="text-muted-foreground">New user? </span>
            <Link href="/register" className="font-medium underline-offset-4 hover:underline">
              Register now
            </Link>
          </div>
        </CardContent>
          <CardFooter className="text-muted-foreground text-xs">
            Protecting your kitchen&apos;s data.
          </CardFooter>
        </Card>
      </div>
    </div>
  );
}
