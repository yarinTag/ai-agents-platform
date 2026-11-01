"""Explicit per-call pricing and session totals, without guessing missing prices."""
import json
import math
import os

NVIDIA_FREE_SOURCE = 'https://docs.api.nvidia.com/nim/docs/product'


def amount(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (ValueError, TypeError):
        return None
    return number if math.isfinite(number) and number >= 0 else None


def pricing(provider, model):
    """Model-specific server rates override provider rates and free-endpoint defaults."""
    catalog = json.loads(os.getenv('PLATFORM_MODEL_PRICING_JSON', '{}'))
    if not isinstance(catalog, dict) or not isinstance(catalog.get(provider, {}), dict):
        raise ValueError('Model pricing must be a provider/model JSON object.')
    record = catalog.get(provider, {}).get(model, {})
    if not isinstance(record, dict):
        raise ValueError('Each model pricing record must be an object.')
    pair = [record.get(key) for key in ('input', 'output')]
    if pair == [None, None]:
        pair = [os.getenv(provider.upper() + suffix) for suffix in
                ('_INPUT_USD_PER_MILLION', '_OUTPUT_USD_PER_MILLION')]
    source = 'CONFIGURED_ESTIMATE'
    if pair == [None, None] and provider == 'direct_nvidia':
        # This runtime uses the fixed NVIDIA-hosted prototyping API, not self-hosted NIM.
        pair, source = [0, 0], 'FREE_ENDPOINT'
    if pair == [None, None]:
        resolved = None
        source = 'UNAVAILABLE'
    else:
        resolved = [amount(value) for value in pair]
        if None in resolved:
            raise ValueError('Configure both finite non-negative input/output token prices.')
    reference = [record.get(key) for key in ('reference_input', 'reference_output')]
    if reference != [None, None]:
        reference = [amount(value) for value in reference]
        if None in reference:
            raise ValueError('Configure both finite non-negative reference token prices.')
    else:
        reference = None
    return {'rates': resolved, 'source': source, 'reference_rates': reference,
            'source_url': NVIDIA_FREE_SOURCE if source == 'FREE_ENDPOINT' else None}


def call_cost(response, policy):
    inputs, outputs = response['input_tokens'], response['output_tokens']
    rate = policy['rates']
    reported = amount(response.get('provider_cost_usd'))
    estimated = (inputs * rate[0] + outputs * rate[1]) / 1_000_000 if rate is not None else None
    cost = reported if reported is not None else estimated
    reference = policy['reference_rates']
    return {'input_tokens': inputs, 'output_tokens': outputs, 'cost_usd': cost,
            'source': 'PROVIDER_REPORTED' if reported is not None else policy['source'],
            'source_url': policy['source_url'],
            'reference_cost_usd': (inputs * reference[0] + outputs * reference[1]) / 1_000_000
                if reference is not None else None,
            'rates_per_million': rate, 'reference_rates_per_million': reference}


def totals(calls, *, prior_unknown=False):
    known = [call['cost_usd'] for call in calls if call.get('cost_usd') is not None]
    complete = not prior_unknown and len(known) == len(calls)
    references = [call['reference_cost_usd'] for call in calls if call.get('reference_cost_usd') is not None]
    cost = sum(known) if complete else None
    sources = {call.get('source') for call in calls}
    return {'cost_usd': cost, 'known_cost_usd': sum(known),
            'status': 'unavailable' if not complete else 'free' if cost == 0 and calls else 'estimated'
                if 'CONFIGURED_ESTIMATE' in sources else 'reported' if calls else 'no_usage',
            'complete': complete, 'calls': len(calls),
            'input_tokens': sum(call.get('input_tokens', 0) for call in calls),
            'output_tokens': sum(call.get('output_tokens', 0) for call in calls),
            'reference_cost_usd': sum(references) if len(references) == len(calls) and calls and not prior_unknown else None}
