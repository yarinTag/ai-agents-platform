/** A failed read stays distinguishable from a successful empty collection. */
export const readResource = async <T>(
  request: Promise<T>,
  apply: (response: T) => void,
  label: string,
): Promise<string | null> => {
  try {
    apply(await request);
    return null;
  } catch {
    return `${label} is unavailable. Retry to refresh this section.`;
  }
};
