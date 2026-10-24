// Session-memory response cache. In-flight requests are shared; failures are never cached.
interface Entry { promise: Promise<unknown>; expiresAt: number }
const entries = new Map<string, Entry>();
const MAX_ENTRIES = 64;

export function cachedRequest<T>(key: string, load: () => Promise<T>, ttlMs: number, force = false): Promise<T> {
  const current = entries.get(key);
  if (!force && current && current.expiresAt > Date.now()) return current.promise as Promise<T>;
  const entry: Entry = { promise: Promise.resolve(), expiresAt: Infinity };
  entry.promise = Promise.resolve().then(load).then(value => {
    entry.expiresAt = Date.now() + ttlMs;
    return value;
  }, error => {
    if (entries.get(key) === entry) entries.delete(key);
    throw error;
  });
  entries.set(key, entry);
  if (entries.size > MAX_ENTRIES) entries.delete(entries.keys().next().value!);
  return entry.promise as Promise<T>;
}

export function invalidateRequestCache(prefix = ''): void {
  for (const key of entries.keys()) if (key.startsWith(prefix)) entries.delete(key);
}
