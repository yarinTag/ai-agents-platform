import { Alert, Descriptions, Space, Tag, Typography } from 'antd';
import { usePrGovernanceText } from '../../i18n/prGovernance';
import { useTranslation } from '../../i18n';

export const record = (value: unknown): Record<string, unknown> =>
  value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
const str = (value: unknown) => typeof value === 'string' ? value : '';
const sha = (value: unknown) => /^(?:[0-9a-f]{40}|[0-9a-f]{64})$/.test(str(value)) ? str(value) : '';
/** Canonical fixed-host links only; model/provider URLs never supply an href. */
export function prLocation(value: unknown) {
  const row = record(value);
  const pull = record(row.pull_request);
  const repository = str(row.repository);
  const number = row.pull_number ?? pull.number;
  if ((!/^[A-Za-z0-9][A-Za-z0-9-]{0,38}\/[A-Za-z0-9_.-]{1,100}$/.test(repository) || ['.', '..'].includes(repository.split('/')[1])) ||
      typeof number !== 'number' || !Number.isSafeInteger(number) || number < 1) return null;
  return { repository, number, url: `https://github.com/${repository}/pull/${number}` };
}
export function PrEvidence({ value }: { value: unknown }) {
  const text = usePrGovernanceText();
  const { dir } = useTranslation();
  const row = record(value);
  const location = prLocation(row);
  if (!location) return null;
  const pull = record(row.pull_request);
  const head = sha(row.head_sha) || sha(record(pull.head).sha);
  const base = sha(row.base_sha) || sha(record(pull.base).sha);
  const evidence = row.evidence_version !== undefined || Array.isArray(row.blockers) || row.candidate_ready !== undefined;
  const proof = row.evidence_version === 2 && (!row.status || row.status === 'COMPLETED');
  const operation = str(row.operation);
  const status = str(row.status);
  const blockers = Array.isArray(row.blockers) ? row.blockers.filter((v): v is string => typeof v === 'string') : [];
  const ready = row.candidate_ready === true && row.review_approved === true && row.base_up_to_date === true &&
    row.required_checks_satisfied === true && row.partial === false && Boolean(head && base) && blockers.length === 0;
  const recovery = (code: string) => {
    if (code === 'REVIEW_APPROVAL_MISSING' || code.includes('reviewer requested')) return text.reviewRecovery;
    if (code === 'BASE_NOT_UP_TO_DATE') return text.baseRecovery;
    if (code.includes('POLICY') || code === 'STRICT_PROTECTED_BASE_REQUIRED') return text.policyRecovery;
    if (code.includes('CHECKS') || code.startsWith('CI ')) return text.ciRecovery;
    if (code.includes('PR_STATE') || code.includes('closed') || code.includes('mergeability')) return text.stateRecovery;
    return text.evidenceRecovery;
  };
  const fact = (v: unknown) => v === true ? text.yes : v === false ? text.no : text.unknown;
  const fields = [
    [text.head, head], [text.base, base], [text.status, text.statuses[status] || status],
    [text.commit, sha(row.merge_commit_sha)], [text.audit, str(row.audit_id)],
    [text.actor, str(row.approved_by)], [text.providerActor, str(row.provider_actor)],
    [text.started, str(row.started_at)], [text.completed, str(row.completed_at)],
  ].filter(([, v]) => v);
  return <section dir={dir} style={{ overflowWrap: 'anywhere', marginBlock: 8 }} aria-label={text.title}>
    <Space wrap>
      <Typography.Link href={location.url} target="_blank" rel="noopener noreferrer"><bdi dir="ltr">{location.repository} #{location.number}</bdi></Typography.Link>
      {operation && <Tag>{operation === 'open_pull_request' ? text.draft : operation === 'merge_pull_request' ? text.merge : operation === 'review_pull_request' ? text.review : operation === 'comment_pull_request' ? text.comment : operation.startsWith('get_pull_request') ? text.read : operation}</Tag>}
      {base && head && <Typography.Link href={`https://github.com/${location.repository}/compare/${base}...${head}`} target="_blank" rel="noopener noreferrer">{text.diff}</Typography.Link>}
    </Space>
    {fields.length > 0 && <Descriptions size="small" column={1} items={fields.map(([label, v]) => ({ key: label, label, children: <bdi dir="ltr">{v}</bdi> }))} />}
    {evidence && <>
      <Typography.Paragraph type="secondary">{text.recorded}</Typography.Paragraph>
      {proof ? <Space wrap>
        <Tag color={ready ? 'success' : 'warning'}>{ready ? text.ready : text.blocked}</Tag>
        <Tag>{text.approved}: {fact(row.review_approved)}</Tag><Tag>{text.checks}: {fact(row.required_checks_satisfied)}</Tag>
        <Tag>{text.currentBase}: {fact(row.base_up_to_date)}</Tag>
      </Space> : <Alert type="info" message={text.legacy} />}
      {row.partial === true && <Alert type="warning" message={text.partial} description={text.evidenceRecovery} />}
      {blockers.map((code, index) => <Alert key={`${code}:${index}`} type="warning" message={text.blockers[code] || <bdi dir="ltr">{code}</bdi>} description={`${text.recovery}: ${recovery(code)}`} />)}
      {Array.isArray(row.reviews) && row.reviews.map((v, i) => {
        const review = record(v);
        return <div key={i}><bdi dir="ltr">{str(review.author)} · {text.statuses[str(review.state)] || str(review.state)} · {sha(review.commit_id)}</bdi> · {text.eligible}: {fact(review.trusted_approval)}</div>;
      })}
    </>}
    {(status === 'STARTED' || status === 'UNKNOWN' || (status === 'FAILED' && ['open_pull_request', 'review_pull_request', 'comment_pull_request'].includes(operation))) && <Alert type="warning" message={text.reconcile} />}
    {status === 'NOT_DISPATCHED' && <Alert type="warning" message={text.notSent} />}
  </section>;
}

/** Only recognized structured results; prose is never promoted to proof. */
export function PrResultEvidence({ value }: { value: unknown }) {
  const row = record(value);
  if (Array.isArray(row.pull_requests)) return <>{row.pull_requests.map((pull, i) =>
    <PrEvidence key={i} value={{ repository: row.repository, pull_request: pull }} />)}</>;
  return <PrEvidence value={row} />;
}

export function PrAuditEvidence({ entries }: { entries: Record<string, unknown>[] }) {
  return <>{entries.map((entry, i) => <PrEvidence key={String(entry.audit_id || i)} value={entry} />)}</>;
}
