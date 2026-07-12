"use client";

import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";

/** Shows the signed-in user and a sign-out action in the dashboard header. */
export function UserMenu() {
  const { me, signOut } = useAuth();
  if (!me) return null;
  return (
    <div className="flex items-center gap-2">
      <span className="text-muted-foreground hidden text-xs sm:inline">
        {me.display_name} · {me.role}
      </span>
      <Button size="sm" variant="ghost" onClick={() => void signOut()}>
        Sign out
      </Button>
    </div>
  );
}
