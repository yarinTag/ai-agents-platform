import type { CostSummary } from '../types/mcp';

export function asCostSummary(value: unknown): CostSummary | undefined {
  if (!value || typeof value !== 'object') return undefined;
  const record = value as Record<string, unknown>;
  return typeof record.status === 'string' && (record.cost_usd === null || typeof record.cost_usd === 'number')
    ? record as unknown as CostSummary : undefined;
}

const dollars = (amount: number) => amount > 0 && amount < 0.000001
  ? '<$0.000001' : `$${amount.toFixed(6)}`;

export function formatCost(summary?: CostSummary | null, legacyCost = 0, locale = 'en'): string {
  const text = locale === 'he'
    ? { unavailable: 'מחיר לא זמין', estimated: 'הערכה', free: 'ללא עלות', noUsage: 'ללא שימוש במודל', reference: 'מחיר ייחוס', reported: 'דווח על ידי הספק' }
    : { unavailable: 'Price unavailable', estimated: 'estimated', free: 'free', noUsage: 'no model usage', reference: 'reference', reported: 'reported' };
  if (!summary) return legacyCost > 0 ? `${dollars(legacyCost)} · ${text.estimated}` : text.unavailable;
  const cost = summary.cost_usd;
  const label = cost == null || summary.status === 'unavailable' ? text.unavailable
    : summary.status === 'free' ? `${dollars(cost)} · ${text.free}`
    : summary.status === 'no_usage' ? `${dollars(cost)} · ${text.noUsage}`
    : `${dollars(cost)} · ${summary.status === 'estimated' ? text.estimated : summary.status === 'reported' ? text.reported : summary.status}`;
  return summary.reference_cost_usd != null
    ? `${label} · ${text.reference} ${dollars(summary.reference_cost_usd)}` : label;
}
