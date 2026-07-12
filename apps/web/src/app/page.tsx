import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { APP_NAME, API_VERSION } from "@rasoi/shared";

export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col items-center justify-center gap-8 p-8">
      <div className="text-center">
        <h1 className="text-4xl font-bold tracking-tight">{APP_NAME}</h1>
        <p className="mt-2 text-muted-foreground">
          Restaurant bulk-ingredient price intelligence.
        </p>
      </div>

      <Card className="w-full">
        <CardHeader>
          <CardTitle>Scaffold ready</CardTitle>
          <CardDescription>
            PR-0 infrastructure is in place. API mounted under{" "}
            <code className="rounded bg-muted px-1 py-0.5 text-sm">/{API_VERSION}</code>.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button asChild>
            <a
              href={`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/healthz`}
              target="_blank"
              rel="noreferrer"
            >
              Check API health
            </a>
          </Button>
        </CardContent>
      </Card>
    </main>
  );
}
