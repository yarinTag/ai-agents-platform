import type { MCPConnector } from '../types/mcp';

/** Canonical configured resource projection; never invent channels on failure. */
export function configuredResourceValues(
  connectors: MCPConnector[], provider: string, arrayKey: string, singleKey: string,
): string[] {
  const values = connectors
    .filter((connector) => connector.provider === provider || connector.id === provider)
    .flatMap((connector) => {
      const configuration = connector.configuration || {};
      const list = Array.isArray(configuration[arrayKey]) ? configuration[arrayKey] : [];
      return [...list, configuration[singleKey]];
    })
    .filter((value): value is string => typeof value === 'string' && Boolean(value.trim()));
  return Array.from(new Set(values.map((value) => value.trim())));
}
