"use client";

import * as React from "react";
import { useRouter } from "next/navigation";

import { fetchMe, logout, type Me, type Role } from "@/lib/auth";

interface AuthContextValue {
  me: Me | null;
  loading: boolean;
  refresh: () => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = React.createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }): React.JSX.Element {
  const router = useRouter();
  const [me, setMe] = React.useState<Me | null>(null);
  const [loading, setLoading] = React.useState<boolean>(true);

  const refresh = React.useCallback(async (): Promise<void> => {
    const next = await fetchMe();
    setMe(next);
  }, []);

  React.useEffect(() => {
    let active = true;
    setLoading(true);
    fetchMe()
      .then((next) => {
        if (active) setMe(next);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const signOut = React.useCallback(async (): Promise<void> => {
    await logout();
    setMe(null);
    router.push("/login");
  }, [router]);

  const value = React.useMemo<AuthContextValue>(
    () => ({ me, loading, refresh, signOut }),
    [me, loading, refresh, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = React.useContext(AuthContext);
  if (ctx === null) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}

export function RequireRole({
  roles,
  children,
  fallback,
}: {
  roles: Role[];
  children: React.ReactNode;
  fallback?: React.ReactNode;
}): React.JSX.Element {
  const { me } = useAuth();
  if (me !== null && roles.includes(me.role)) {
    return <>{children}</>;
  }
  return <>{fallback ?? null}</>;
}

export function DashboardGuard({ children }: { children: React.ReactNode }): React.JSX.Element {
  const { me, loading } = useAuth();
  const router = useRouter();

  React.useEffect(() => {
    if (!loading && me === null) {
      router.replace("/login");
    }
  }, [loading, me, router]);

  if (loading) {
    return (
      <div className="text-muted-foreground grid min-h-screen place-items-center">Loading…</div>
    );
  }

  if (me === null) {
    return <></>;
  }

  return <>{children}</>;
}
