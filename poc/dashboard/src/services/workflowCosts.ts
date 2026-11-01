import type { CostSummary } from '../types/mcp';

export function asCostSummary(value: unknown): CostSummary | undefined {
  if (!value || typeof value !== 'object') return undefined;
  const record = value as Record<string, unknown>;
  return typeof record.status === 'string' && (record.cost_usd === null || typeof record.cost_usd === 'number')
    ? record as unknown as CostSummary : undefined;
}

const dollars = (amount: number) => amount > 0 && amount < 0.000001
  ? '<$0.000001' : `$${amount.toFixed(6)}`;

export function formatCost(summary?: CostSummary | null, legacyCost = 0): string {
  if (!summary) return legacyCost > 0 ? `${dollars(legacyCost)} · estimated` : 'Price unavailable';
  const cost = summary.cost_usd;
  const label = cost == null || summary.status === 'unavailable' ? 'Price unavailable'
    : summary.status === 'free' ? `${dollars(cost)} · free`
    : summary.status === 'no_usage' ? `${dollars(cost)} · no model usage`
    : `${dollars(cost)} · ${summary.status}`;
  return summary.reference_cost_usd != null
    ? `${label} · reference ${dollars(summary.reference_cost_usd)}` : label;
}
