"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

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
    <div className="grid min-h-screen place-items-center p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Rasoi Radar</CardTitle>
          <CardDescription>Sign in</CardDescription>
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
          Protecting your kitchen’s data.
        </CardFooter>
      </Card>
    </div>
  );
}
