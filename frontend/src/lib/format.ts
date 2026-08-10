const usd = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

const usdCents = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function formatUsd(value: number, cents = false): string {
  return cents ? usdCents.format(value) : usd.format(value);
}

export function formatDeltaPct(actual: number, expected: number): string {
  if (expected === 0) return "—";
  const pct = ((actual - expected) / expected) * 100;
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(1)}%`;
}

export function formatTime(ts: string): string {
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return ts;
  return d.toLocaleTimeString("en-US", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

/** Shorten a DataHub-style urn to its dataset name for compact display. */
export function shortUrn(urn: string): string {
  const match = urn.match(/,([^,]+),[A-Z]+\)$/);
  return match ? match[1] : urn;
}
