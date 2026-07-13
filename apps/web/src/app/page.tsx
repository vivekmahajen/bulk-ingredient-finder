import Link from "next/link";
import {
  ArrowRight,
  Boxes,
  Camera,
  Check,
  Languages,
  LineChart,
  MapPin,
  ShieldCheck,
} from "lucide-react";
import { Logo, LogoMark } from "@/components/brand";
import { Button } from "@/components/ui/button";

const FEATURES = [
  {
    icon: Camera,
    title: "Invoice capture",
    body: "Photograph any supplier invoice — SWAD, Laxmi, a Spanish produce house, a thermal receipt. Claude vision reads the line items OCR chokes on.",
  },
  {
    icon: Languages,
    title: "Any language, one catalog",
    body: "हल्दी, jeera, cumin — they all resolve to the same item. Search and match ingredients in Hindi, Spanish, or English.",
  },
  {
    icon: MapPin,
    title: "Cheapest within your radius",
    body: "Compare normalized $/kg across every supplier that delivers or sits inside your drive radius. No more guessing which run is worth it.",
  },
  {
    icon: Boxes,
    title: "Bulk pricing that adds up",
    body: "Case packs, catch-weight, 6/#10 — normalized to a true unit price so a 40 lb case and a gallon jug compare honestly.",
  },
  {
    icon: LineChart,
    title: "Price history & forecasts",
    body: "Track how each ingredient moves over time, plan demand month by month, and catch a supplier creeping up on you.",
  },
  {
    icon: ShieldCheck,
    title: "Reviewed, never guessed",
    body: "Extraction proposes; a human confirms. Confidence is shown everywhere and nothing enters your price map unreviewed.",
  },
];

const STEPS = [
  {
    n: "01",
    title: "Snap the invoice",
    body: "Open the app on your phone in the walk-in, point the camera, and upload. HEIC, PDF, thermal — all fine.",
  },
  {
    n: "02",
    title: "Review the lines",
    body: "See the original script beside the English rendering, the live $/kg, and a confidence badge on every number.",
  },
  {
    n: "03",
    title: "Commit to your map",
    body: "One tap turns reviewed lines into price entries — feeding compare, history, and your true food cost.",
  },
];

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col">
      {/* Header */}
      <header className="border-border/70 bg-background/80 sticky top-0 z-40 border-b backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
          <Logo />
          <nav className="text-muted-foreground hidden items-center gap-8 text-sm font-medium md:flex">
            <a href="#features" className="hover:text-foreground transition-colors">
              Features
            </a>
            <a href="#how" className="hover:text-foreground transition-colors">
              How it works
            </a>
            <a href="#why" className="hover:text-foreground transition-colors">
              Why Rasoi
            </a>
          </nav>
          <div className="flex items-center gap-2">
            <Button asChild variant="ghost" size="sm">
              <Link href="/login">Log in</Link>
            </Button>
            <Button asChild size="sm">
              <Link href="/register">
                Get started
                <ArrowRight className="ml-1 h-4 w-4" />
              </Link>
            </Button>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="grid-fade pointer-events-none absolute inset-0 opacity-60 [mask-image:radial-gradient(ellipse_at_top,black,transparent_70%)]" />
        <div className="relative mx-auto grid max-w-6xl items-center gap-12 px-4 py-16 sm:px-6 lg:grid-cols-2 lg:py-24">
          <div>
            <span className="border-border bg-accent text-accent-foreground inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium">
              <span className="bg-primary h-1.5 w-1.5 rounded-full" />
              Invoice capture now live — in any language
            </span>
            <h1 className="mt-5 text-4xl font-bold tracking-tight text-balance sm:text-5xl lg:text-6xl">
              Know your true food cost, <span className="text-gradient">in any language</span>.
            </h1>
            <p className="text-muted-foreground mt-5 max-w-xl text-lg">
              Rasoi Radar turns a photo of any supplier invoice into tracked prices — then shows you
              the cheapest place to buy every bulk ingredient, across suppliers, in the language your
              kitchen actually speaks.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Button asChild size="lg">
                <Link href="/register">
                  Start free
                  <ArrowRight className="ml-1.5 h-4 w-4" />
                </Link>
              </Button>
              <Button asChild size="lg" variant="outline">
                <Link href="/login">See the dashboard</Link>
              </Button>
            </div>
            <div className="text-muted-foreground mt-6 flex flex-wrap gap-x-6 gap-y-2 text-sm">
              {["No card required", "English · हिन्दी · Español", "Reviewed before it counts"].map(
                (t) => (
                  <span key={t} className="flex items-center gap-1.5">
                    <Check className="text-primary h-4 w-4" />
                    {t}
                  </span>
                ),
              )}
            </div>
          </div>

          {/* Hero visual — a stylized "cheapest now" answer card. */}
          <div className="relative">
            <div className="bg-brand-gradient absolute -inset-4 -z-10 rounded-3xl opacity-15 blur-2xl" />
            <div className="border-border bg-card rounded-2xl border p-5 shadow-xl shadow-slate-900/5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <LogoMark className="h-6 w-6" />
                  <span className="text-sm font-semibold">Cheapest now</span>
                </div>
                <span className="bg-accent text-accent-foreground rounded-full px-2 py-0.5 text-xs font-medium">
                  within 25 mi
                </span>
              </div>
              <div className="mt-4">
                <div className="text-muted-foreground text-xs">Basmati rice (dry)</div>
                <div className="mt-1 text-3xl font-bold tracking-tight">
                  $1.28<span className="text-muted-foreground text-lg font-medium">/kg</span>
                </div>
                <div className="text-muted-foreground text-sm">
                  @ SWAD Wholesale · 20&nbsp;kg bag · 34% under the priciest
                </div>
              </div>
              <div className="mt-5 space-y-2">
                {[
                  ["SWAD Wholesale", "$1.28/kg", true],
                  ["Restaurant Depot", "$1.51/kg", false],
                  ["Patel Bros", "$1.74/kg", false],
                ].map(([name, price, best]) => (
                  <div
                    key={name as string}
                    className={`flex items-center justify-between rounded-lg border px-3 py-2 text-sm ${
                      best ? "border-primary/40 bg-accent" : "border-border"
                    }`}
                  >
                    <span className="font-medium">{name}</span>
                    <span className="font-mono">{price}</span>
                  </div>
                ))}
              </div>
              <div className="border-border mt-5 flex items-center gap-3 rounded-lg border border-dashed p-3">
                <Camera className="text-primary h-5 w-5 shrink-0" />
                <p className="text-muted-foreground text-xs">
                  Captured from a photographed invoice — <span lang="hi">बासमती चावल</span> → basmati
                  rice, reviewed and committed.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Trust strip */}
      <section className="border-border/70 border-y">
        <div className="text-muted-foreground mx-auto flex max-w-6xl flex-wrap items-center justify-center gap-x-8 gap-y-2 px-4 py-6 text-sm sm:px-6">
          <span className="text-xs font-medium uppercase tracking-wide">
            Built for the invoices OCR can&apos;t read
          </span>
          {["Ethnic wholesale", "Cash & carry", "Produce houses", "Broadline", "Thermal receipts"].map(
            (t) => (
              <span key={t} className="font-medium">
                {t}
              </span>
            ),
          )}
        </div>
      </section>

      {/* Features */}
      <section id="features" className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Everything a multilingual kitchen needs to control cost
          </h2>
          <p className="text-muted-foreground mt-4 text-lg">
            The back-office tooling MarginEdge and xtraCHEF built — rebuilt for the suppliers and
            languages they never covered.
          </p>
        </div>
        <div className="mt-14 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map(({ icon: Icon, title, body }) => (
            <div
              key={title}
              className="border-border bg-card hover:border-primary/40 group rounded-2xl border p-6 transition-colors"
            >
              <div className="bg-accent text-accent-foreground flex h-11 w-11 items-center justify-center rounded-xl">
                <Icon className="h-5 w-5" />
              </div>
              <h3 className="mt-4 text-lg font-semibold">{title}</h3>
              <p className="text-muted-foreground mt-2 text-sm leading-relaxed">{body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="bg-muted/40 border-border/70 border-y">
        <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
              From walk-in photo to true cost in three taps
            </h2>
          </div>
          <div className="mt-14 grid gap-8 md:grid-cols-3">
            {STEPS.map((s) => (
              <div key={s.n} className="relative">
                <div className="text-primary/25 text-5xl font-bold">{s.n}</div>
                <h3 className="mt-2 text-lg font-semibold">{s.title}</h3>
                <p className="text-muted-foreground mt-2 text-sm leading-relaxed">{s.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Why / honesty band */}
      <section id="why" className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
        <div className="border-border bg-card grid items-center gap-8 rounded-3xl border p-8 sm:p-12 lg:grid-cols-2">
          <div>
            <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
              Wrong is worse than empty.
            </h2>
            <p className="text-muted-foreground mt-4">
              Every extracted line shows its confidence. Stale and uncertain data is demoted, not
              hidden. Extraction proposes — a human commits. No price enters your market map
              unreviewed, so the numbers you act on are numbers you trust.
            </p>
          </div>
          <ul className="space-y-3">
            {[
              "Original invoice script kept beside the English rendering",
              "Normalized $/kg, $/L, $/each — compare packs honestly",
              "Full provenance: every price links back to its invoice line",
              "Your data stays yours — org-scoped and private by default",
            ].map((t) => (
              <li key={t} className="flex items-start gap-3">
                <span className="bg-accent text-accent-foreground mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full">
                  <Check className="h-3 w-3" />
                </span>
                <span className="text-sm">{t}</span>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* CTA band */}
      <section className="mx-auto w-full max-w-6xl px-4 pb-20 sm:px-6">
        <div className="bg-brand-gradient relative overflow-hidden rounded-3xl px-8 py-14 text-center sm:px-12">
          <div className="relative">
            <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
              Start tracking your real food cost today
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-teal-50">
              Free to start. Photograph your next invoice and watch it become a price your whole
              team can compare.
            </p>
            <div className="mt-8 flex flex-wrap justify-center gap-3">
              <Button asChild size="lg" variant="secondary">
                <Link href="/register">
                  Create your account
                  <ArrowRight className="ml-1.5 h-4 w-4" />
                </Link>
              </Button>
              <Button
                asChild
                size="lg"
                variant="outline"
                className="border-white/30 bg-transparent text-white hover:bg-white/10 hover:text-white"
              >
                <Link href="/login">Log in</Link>
              </Button>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-border/70 mt-auto border-t">
        <div className="text-muted-foreground mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-4 py-8 text-sm sm:flex-row sm:px-6">
          <Logo textClassName="text-base" />
          <p>© {2026} Rasoi Radar. Restaurant cost control, in any language.</p>
        </div>
      </footer>
    </div>
  );
}
