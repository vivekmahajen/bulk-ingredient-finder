"use client";

import { useMemo } from "react";
import type { StoreSeries } from "@/lib/prices";

/**
 * Lightweight dependency-free multi-series line chart of unit price over time,
 * one line per store. Values are cents-per-base-unit; the Y axis shows dollars.
 */

// Accessible, distinguishable in light + dark. Swap for a brand palette later.
const SERIES_COLORS = ["#2563eb", "#16a34a", "#d97706", "#9333ea", "#dc2626", "#0891b2"];

const W = 640;
const H = 260;
const PAD = { top: 16, right: 16, bottom: 28, left: 44 };

interface Pt {
  x: number;
  y: number;
  dollars: number;
  date: string;
  stale: boolean;
  store: string;
}

export function PriceHistoryChart({ series }: { series: StoreSeries[] }) {
  const model = useMemo(() => {
    const all = series.flatMap((s) =>
      s.points
        .filter((p) => p.unit_price_cents != null)
        .map((p) => ({ t: new Date(p.observed_at).getTime(), v: p.unit_price_cents as number })),
    );
    if (all.length === 0) return null;

    const times = all.map((a) => a.t);
    const vals = all.map((a) => a.v);
    const tMin = Math.min(...times);
    const tMax = Math.max(...times);
    const vMin = 0;
    const vMax = Math.max(...vals) * 1.1 || 1;

    const sx = (t: number) =>
      PAD.left + (tMax === tMin ? 0.5 : (t - tMin) / (tMax - tMin)) * (W - PAD.left - PAD.right);
    const sy = (v: number) =>
      H - PAD.bottom - ((v - vMin) / (vMax - vMin)) * (H - PAD.top - PAD.bottom);

    const lines = series.map((s, i) => {
      const pts: Pt[] = s.points
        .filter((p) => p.unit_price_cents != null)
        .map((p) => ({
          x: sx(new Date(p.observed_at).getTime()),
          y: sy(p.unit_price_cents as number),
          dollars: (p.unit_price_cents as number) / 100,
          date: p.observed_at,
          stale: p.stale,
          store: s.store_name,
        }));
      return { store: s.store_name, color: SERIES_COLORS[i % SERIES_COLORS.length], pts };
    });

    const yTicks = [0, 0.25, 0.5, 0.75, 1].map((f) => {
      const v = vMin + f * (vMax - vMin);
      return { y: sy(v), label: `$${(v / 100).toFixed(2)}` };
    });

    return { lines, yTicks };
  }, [series]);

  if (!model) {
    return <p className="text-muted-foreground text-sm">No price history to chart yet.</p>;
  }

  return (
    <div className="w-full overflow-x-auto">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="h-auto w-full min-w-[480px]"
        role="img"
        aria-label="Price history"
      >
        {model.yTicks.map((t, i) => (
          <g key={i}>
            <line
              x1={PAD.left}
              x2={W - PAD.right}
              y1={t.y}
              y2={t.y}
              className="stroke-border"
              strokeWidth={1}
            />
            <text x={4} y={t.y + 4} className="fill-muted-foreground text-[10px]">
              {t.label}
            </text>
          </g>
        ))}
        {model.lines.map((line) => (
          <g key={line.store}>
            {line.pts.length > 1 && (
              <polyline
                fill="none"
                stroke={line.color}
                strokeWidth={2}
                points={line.pts.map((p) => `${p.x},${p.y}`).join(" ")}
              />
            )}
            {line.pts.map((p, i) => (
              <circle
                key={i}
                cx={p.x}
                cy={p.y}
                r={p.stale ? 5 : 3.5}
                fill={p.stale ? "transparent" : line.color}
                stroke={line.color}
                strokeWidth={p.stale ? 2 : 0}
                strokeDasharray={p.stale ? "2 2" : undefined}
              >
                <title>{`${p.store} · ${p.date} · $${p.dollars.toFixed(2)}${p.stale ? " (stale)" : ""}`}</title>
              </circle>
            ))}
          </g>
        ))}
      </svg>
      <div className="mt-2 flex flex-wrap gap-3">
        {model.lines.map((line) => (
          <span key={line.store} className="inline-flex items-center gap-1.5 text-xs">
            <span
              className="inline-block h-2 w-2 rounded-full"
              style={{ background: line.color }}
            />
            {line.store}
          </span>
        ))}
      </div>
    </div>
  );
}
