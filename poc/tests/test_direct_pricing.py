"""Pricing/session accounting contracts without inference or mocked transports."""
import json
import pytest
from runtime.direct_pricing import call_cost, pricing, totals
from runtime.direct_sessions import DirectSession
from backend.api.workflow_costs import task_cost


def clear_prices(monkeypatch, provider):
    monkeypatch.delenv('PLATFORM_MODEL_PRICING_JSON', raising=False)
    for suffix in ('_INPUT_USD_PER_MILLION', '_OUTPUT_USD_PER_MILLION'):
        monkeypatch.delenv(provider.upper() + suffix, raising=False)


def test_missing_price_is_distinct_from_explicit_free(monkeypatch):
    clear_prices(monkeypatch, 'direct_openai')
    policy = pricing('direct_openai', 'model')
    response = {'input_tokens': 100, 'output_tokens': 20}
    assert totals([call_cost(response, policy)])['status'] == 'unavailable'
    monkeypatch.setenv('DIRECT_OPENAI_INPUT_USD_PER_MILLION', '0')
    monkeypatch.setenv('DIRECT_OPENAI_OUTPUT_USD_PER_MILLION', '0')
    summary = totals([call_cost(response, pricing('direct_openai', 'model'))])
    assert summary['status'] == 'free'
    assert summary['cost_usd'] == 0


def test_nvidia_free_hosted_endpoint_has_explicit_provenance(monkeypatch):
    clear_prices(monkeypatch, 'direct_nvidia')
    policy = pricing('direct_nvidia', 'nvidia/model')
    assert policy['source'] == 'FREE_ENDPOINT'
    assert policy['rates'] == [0, 0]
    assert policy['source_url'].startswith('https://docs.api.nvidia.com/')


def test_model_rates_and_reference_price_are_separate_from_provider_charge(monkeypatch):
    clear_prices(monkeypatch, 'direct_openrouter')
    monkeypatch.setenv('PLATFORM_MODEL_PRICING_JSON', json.dumps({'direct_openrouter': {
        'model-a': {'input': 2, 'output': 8, 'reference_input': 3, 'reference_output': 12},
        'model-b': {'input': 4, 'output': 16}}}))
    response = {'input_tokens': 1_000_000, 'output_tokens': 500_000, 'provider_cost_usd': 0}
    call = call_cost(response, pricing('direct_openrouter', 'model-a'))
    assert call['cost_usd'] == 0  # A real provider zero must not fall back to the estimate.
    assert call['reference_cost_usd'] == 9
    assert call['source'] == 'PROVIDER_REPORTED'
    assert totals([call])['reference_cost_usd'] == 9
    assert pricing('direct_openrouter', 'model-b')['rates'] == [4, 16]
    assert pricing('direct_openrouter', 'unknown-model')['rates'] is None


def test_incomplete_pricing_totals_do_not_hide_known_spend(monkeypatch):
    clear_prices(monkeypatch, 'direct_openai')
    policy = pricing('direct_openai', 'model')
    unknown = call_cost({'input_tokens': 10, 'output_tokens': 2}, policy)
    known = call_cost({'input_tokens': 10, 'output_tokens': 2, 'provider_cost_usd': 0.25}, policy)
    summary = totals([unknown, known])
    assert summary['cost_usd'] is None
    assert summary['known_cost_usd'] == 0.25
    assert summary['input_tokens'] == 20
    assert not summary['complete']


def test_partial_or_invalid_rates_are_rejected(monkeypatch):
    clear_prices(monkeypatch, 'direct_openai')
    monkeypatch.setenv('DIRECT_OPENAI_INPUT_USD_PER_MILLION', '1')
    with pytest.raises(ValueError):
        pricing('direct_openai', 'model')
    monkeypatch.setenv('DIRECT_OPENAI_OUTPUT_USD_PER_MILLION', 'NaN')
    with pytest.raises(ValueError):
        pricing('direct_openai', 'model')


def test_session_accounting_survives_resume_but_fork_starts_new_spend(tmp_path, monkeypatch):
    monkeypatch.setenv('PLATFORM_API_SESSION_DIR', str(tmp_path))
    monkeypatch.setenv('PLATFORM_API_SESSION_SCOPE', 'tenant:agent')
    session = DirectSession('direct_openai', 'model')
    session.messages.append({'role': 'user', 'content': 'Context'})
    session.usage_calls.append({'cost_usd': 0.25, 'input_tokens': 10, 'output_tokens': 2})
    session.save()
    resumed = DirectSession('direct_openai', 'model', session.id)
    resumed.usage_calls.append({'cost_usd': 0.5, 'input_tokens': 20, 'output_tokens': 3})
    assert totals(resumed.usage_calls)['cost_usd'] == 0.75
    fork = DirectSession('direct_openai', 'model', session.id, fork=True)
    assert fork.messages == session.messages
    assert fork.usage_calls == []
    record = json.loads(session.path(session.id).read_text())
    record.pop('usage_calls')
    session.path(session.id).write_text(json.dumps(record))
    legacy = DirectSession('direct_openai', 'model', session.id)
    assert legacy.prior_usage_unknown
    assert not totals(legacy.usage_calls, prior_unknown=legacy.prior_usage_unknown)['complete']


def test_historical_zero_without_pricing_is_not_declared_free():
    assert task_cost([], 0, 100, 20)['status'] == 'unavailable'
    assert task_cost([], 0, 0, 0)['status'] == 'no_usage'
    assert task_cost([], 0.2, 100, 20)['cost_usd'] == 0.2
