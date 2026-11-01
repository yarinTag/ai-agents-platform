/**
 * Client-side mirrors of the server's workflow settings/secret rules (poc/workflows/settings.py,
 * poc/integrations/workflow_secrets.py). These give early feedback only; the server is authoritative.
 */
import axios from 'axios';

/** Select value representing "platform default"; saved as `model: null`. */
export const PLATFORM_DEFAULT_MODEL = 'default';
export const MAX_SECRET_VALUE_BYTES = 32768;
export const MAX_EXTERNAL_REF_LENGTH = 600;

const SECRET_NAME_PATTERN = /^[A-Z_][A-Z0-9_]{0,63}$/;
/** Names that would change sandbox/proxy behaviour; mirrors the server's reserved set. */
const RESERVED_SECRET_NAMES = new Set([
  'PATH', 'HOME', 'USER', 'SHELL', 'PWD', 'HOSTNAME', 'LANG', 'TERM', 'TMPDIR', 'HTTP_PROXY', 'HTTPS_PROXY',
  'NO_PROXY', 'ALL_PROXY', 'LD_PRELOAD', 'LD_LIBRARY_PATH', 'PYTHONPATH', 'PYTHONHOME', 'NODE_OPTIONS',
  'BASH_ENV', 'ENV',
]);
const SECRET_ARN_PATTERN = /^arn:aws:secretsmanager:[a-z0-9-]+:\d{12}:secret:[A-Za-z0-9/_+=.@-]{1,512}$/;
const HOSTNAME_PATTERN = /^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$/;

export type SecretNameProblem = 'format' | 'reserved' | null;

export const secretNameProblem = (name: string): SecretNameProblem => {
  if (!SECRET_NAME_PATTERN.test(name)) return 'format';
  // DOCKER_* would redirect the docker CLI that receives secrets through its environment.
  if (name.startsWith('PLATFORM_') || name.startsWith('DOCKER_') || RESERVED_SECRET_NAMES.has(name)) return 'reserved';
  return null;
};

export const secretValueBytes = (value: string): number => new TextEncoder().encode(value).length;

export const isSecretArn = (ref: string): boolean =>
  ref.length <= MAX_EXTERNAL_REF_LENGTH && SECRET_ARN_PATTERN.test(ref);

/** Same normalization as the server: trim, lowercase, drop trailing dots, de-duplicate. */
export const normalizeHosts = (hosts: readonly string[]): string[] => {
  const normalized: string[] = [];
  for (const host of hosts) {
    const value = host.trim().toLowerCase().replace(/\.+$/, '');
    if (value && !normalized.includes(value)) normalized.push(value);
  }
  return normalized;
};

/** Exact hostname only: no scheme, port, path, IP address or wildcard. */
export const isValidHost = (host: string): boolean => HOSTNAME_PATTERN.test(host);

export const toModelValue = (model: string | null | undefined): string =>
  model && model !== PLATFORM_DEFAULT_MODEL ? model : PLATFORM_DEFAULT_MODEL;

export const fromModelValue = (value: string): string | null =>
  value === PLATFORM_DEFAULT_MODEL ? null : value;

/** "4g" -> "4 GB", "512m" -> "512 MB"; anything else is shown as sent by the server. */
export const formatMemory = (memory: string): string => {
  const match = /^(\d+)([gm])$/i.exec(memory.trim());
  if (!match) return memory;
  return `${match[1]} ${match[2].toLowerCase() === 'g' ? 'GB' : 'MB'}`;
};

export const formatTimestamp = (value: string): string => {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
};

export interface ApiFailure {
  status?: number;
  detail?: string;
}

/**
 * Extract a displayable status/detail from an API error. FastAPI 422 bodies echo the submitted
 * `input`, which may be a secret value, so only the `msg` text of each validation entry is used.
 * The error object itself (whose request config holds the body) is never stored or logged.
 */
export const describeApiFailure = (cause: unknown): ApiFailure => {
  if (!axios.isAxiosError(cause)) return {};
  const status = cause.response?.status;
  const body: unknown = cause.response?.data;
  const detail = body && typeof body === 'object' ? (body as { detail?: unknown }).detail : undefined;
  if (typeof detail === 'string') return { status, detail };
  if (Array.isArray(detail)) {
    const messages = detail
      .map((entry: unknown) => (entry && typeof entry === 'object' ? (entry as { msg?: unknown }).msg : undefined))
      .filter((msg): msg is string => typeof msg === 'string' && msg.length > 0);
    return { status, detail: messages.length ? messages.join('; ') : undefined };
  }
  if (detail && typeof detail === 'object') {
    const text = (detail as { message?: unknown }).message;
    if (typeof text === 'string') return { status, detail: text };
  }
  return { status };
};
