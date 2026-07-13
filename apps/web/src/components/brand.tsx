import { cn } from "@/lib/utils";

/** The Rasoi Radar mark — concentric radar sweep with a locator dot. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      className={cn("h-7 w-7", className)}
      fill="none"
      aria-hidden="true"
    >
      <rect width="32" height="32" rx="8" className="fill-primary" />
      <circle cx="16" cy="16" r="10" className="stroke-primary-foreground/35" strokeWidth="1.5" />
      <circle cx="16" cy="16" r="6" className="stroke-primary-foreground/55" strokeWidth="1.5" />
      <path
        d="M16 16 L24 9 A10 10 0 0 1 24 23 Z"
        className="fill-primary-foreground/25"
      />
      <circle cx="16" cy="16" r="2.4" className="fill-primary-foreground" />
    </svg>
  );
}

export function Logo({
  className,
  textClassName,
}: {
  className?: string;
  textClassName?: string;
}) {
  return (
    <span className={cn("flex items-center gap-2", className)}>
      <LogoMark />
      <span className={cn("text-lg font-semibold tracking-tight", textClassName)}>
        Rasoi Radar
      </span>
    </span>
  );
}
