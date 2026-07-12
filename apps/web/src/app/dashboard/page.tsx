import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function DashboardHome() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground">Restaurant bulk-ingredient price intelligence.</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <Link href="/dashboard/ingredients">
          <Card className="transition-colors hover:border-foreground/30">
            <CardHeader>
              <CardTitle>Ingredients</CardTitle>
              <CardDescription>Your multilingual catalog — add and search.</CardDescription>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              Add an ingredient in any language; we translate and make it searchable.
            </CardContent>
          </Card>
        </Link>
        <Link href="/dashboard/stores">
          <Card className="transition-colors hover:border-foreground/30">
            <CardHeader>
              <CardTitle>Stores</CardTitle>
              <CardDescription>Suppliers you buy from.</CardDescription>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              Broadline, cash-and-carry, and ethnic-wholesale suppliers.
            </CardContent>
          </Card>
        </Link>
      </div>
    </div>
  );
}
