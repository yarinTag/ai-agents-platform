"""Direct HTTP provider metadata and model catalog; credentials remain on the server."""
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

DIRECT_PROVIDERS = {
    'direct_nvidia': ('NVIDIA NIM', 'NVIDIA_API_KEY', 'https://integrate.api.nvidia.com/v1'),
    'direct_anthropic': ('Anthropic', 'ANTHROPIC_API_KEY', 'https://api.anthropic.com/v1'),
    'direct_openai': ('OpenAI', 'OPENAI_API_KEY', 'https://api.openai.com/v1'),
    'direct_openrouter': ('OpenRouter', 'OPENROUTER_API_KEY', 'https://openrouter.ai/api/v1'),
}

DEFAULT_PROVIDER_MODEL: Dict[str, str] = {
    'direct_nvidia': 'nvidia/nemotron-3.5-super-vl-120b-a12b',
    'direct_anthropic': 'claude-3-7-sonnet-20250219',
    'direct_openai': 'gpt-4o',
    'direct_openrouter': 'qwen/qwen3.8-27b:free',
}

PROVIDER_MODELS: Dict[str, List[Dict[str, Any]]] = {
    'direct_nvidia': [
        {
            'id': 'nvidia/nemotron-3.5-super-vl-120b-a12b',
            'name': 'Nemotron 3.5 Super 120B',
            'provider': 'NVIDIA NIM',
            'description': 'High-intelligence flagship 120B reasoning and coding model on NVIDIA NIM',
            'context_window': 128000,
            'tier': 'executive',
        },
        {
            'id': 'nvidia/nemotron-3-ultra-550b-a55b',
            'name': 'Nemotron 3 Ultra 550B',
            'provider': 'NVIDIA NIM',
            'description': 'Frontier 550B MoE model for architecture, planning, and complex reasoning',
            'context_window': 128000,
            'tier': 'architect',
        },
        {
            'id': 'nvidia/nemotron-3.5-lightning-30b-a3b',
            'name': 'Nemotron 3.5 Lightning 30B',
            'provider': 'NVIDIA NIM',
            'description': 'High-speed reasoning and tool-calling model on NVIDIA NIM',
            'context_window': 128000,
            'tier': 'developer',
        },
        {
            'id': 'nvidia/nemotron-3.5-bolt-e4b',
            'name': 'Nemotron 3.5 Bolt',
            'provider': 'NVIDIA NIM',
            'description': 'Ultra-low-latency model (~0.4s) ideal for fast worker tasks and connection checks',
            'context_window': 128000,
            'tier': 'worker',
        },
        {
            'id': 'mistralai/mistral-large-4-1t-a52b',
            'name': 'Mistral Large 4 (1T MoE)',
            'provider': 'NVIDIA NIM',
            'description': 'Flagship Mistral 1T MoE model hosted on NVIDIA NIM infrastructure',
            'context_window': 128000,
            'tier': 'executive',
        },
        {
            'id': 'poolside/laguna-xs-2.1',
            'name': 'Poolside Laguna XS 2.1',
            'provider': 'NVIDIA NIM',
            'description': 'Specialized software engineering and code generation model on NVIDIA NIM',
            'context_window': 128000,
            'tier': 'developer',
        },
    ],
    'direct_anthropic': [
        {
            'id': 'claude-sonnet-4-20250514',
            'name': 'Claude Sonnet 4',
            'provider': 'Anthropic',
            'description': 'Next-generation flagship Claude model for complex agentic workflows',
            'context_window': 200000,
            'tier': 'executive',
        },
        {
            'id': 'claude-3-7-sonnet-20250219',
            'name': 'Claude 3.7 Sonnet',
            'provider': 'Anthropic',
            'description': 'Hybrid reasoning model combining instant answers with step-by-step thinking',
            'context_window': 200000,
            'tier': 'executive',
        },
        {
            'id': 'claude-3-5-sonnet-20241022',
            'name': 'Claude 3.5 Sonnet',
            'provider': 'Anthropic',
            'description': 'High-intelligence flagship model optimized for software engineering and coding',
            'context_window': 200000,
            'tier': 'developer',
        },
        {
            'id': 'claude-3-5-haiku-20241022',
            'name': 'Claude 3.5 Haiku',
            'provider': 'Anthropic',
            'description': 'Ultra-fast, lightweight model ideal for quick subtasks and high throughput',
            'context_window': 200000,
            'tier': 'worker',
        },
        {
            'id': 'claude-3-opus-20240229',
            'name': 'Claude 3 Opus',
            'provider': 'Anthropic',
            'description': 'Deep contextual synthesis and high-level architectural planning',
            'context_window': 200000,
            'tier': 'architect',
        },
    ],
    'direct_openai': [
        {
            'id': 'gpt-4.1',
            'name': 'GPT-4.1',
            'provider': 'OpenAI',
            'description': 'Flagship OpenAI model for complex coding, tool calling, and long-context reasoning',
            'context_window': 128000,
            'tier': 'executive',
        },
        {
            'id': 'gpt-4o',
            'name': 'GPT-4o',
            'provider': 'OpenAI',
            'description': 'Fast, versatile flagship model for software development and orchestration',
            'context_window': 128000,
            'tier': 'developer',
        },
        {
            'id': 'gpt-4.1-mini',
            'name': 'GPT-4.1 Mini',
            'provider': 'OpenAI',
            'description': 'Low-latency, cost-efficient model for worker tasks and rapid execution',
            'context_window': 128000,
            'tier': 'worker',
        },
        {
            'id': 'gpt-4o-mini',
            'name': 'GPT-4o Mini',
            'provider': 'OpenAI',
            'description': 'Lightweight high-throughput model for fast subtasks',
            'context_window': 128000,
            'tier': 'worker',
        },
        {
            'id': 'o3-mini',
            'name': 'o3-mini',
            'provider': 'OpenAI',
            'description': 'Reasoning-optimized model for architecture, logic, and verification',
            'context_window': 200000,
            'tier': 'architect',
        },
    ],
    'direct_openrouter': [
        {
            'id': 'qwen/qwen3.8-27b:free',
            'name': 'Qwen 3.8 27B (Free)',
            'provider': 'OpenRouter',
            'description': 'Free-tier general instruction and coding model via OpenRouter',
            'context_window': 128000,
            'tier': 'worker',
        },
        {
            'id': 'anthropic/claude-3.7-sonnet',
            'name': 'Claude 3.7 Sonnet (OpenRouter)',
            'provider': 'OpenRouter',
            'description': 'Anthropic Claude 3.7 Sonnet routed through OpenRouter',
            'context_window': 200000,
            'tier': 'executive',
        },
        {
            'id': 'openai/gpt-4o',
            'name': 'GPT-4o (OpenRouter)',
            'provider': 'OpenRouter',
            'description': 'OpenAI GPT-4o routed through OpenRouter',
            'context_window': 128000,
            'tier': 'developer',
        },
        {
            'id': 'meta-llama/llama-3.3-70b-instruct',
            'name': 'Llama 3.3 70B Instruct (OpenRouter)',
            'provider': 'OpenRouter',
            'description': 'Meta Llama 3.3 70B Instruct via OpenRouter',
            'context_window': 128000,
            'tier': 'worker',
        },
        {
            'id': 'deepseek/deepseek-r1',
            'name': 'DeepSeek R1 (OpenRouter)',
            'provider': 'OpenRouter',
            'description': 'DeepSeek R1 reasoning model via OpenRouter',
            'context_window': 128000,
            'tier': 'architect',
        },
    ],
}


def model_setting(provider: str) -> str:
    return 'runtime_model_' + provider


def api_key_setting(provider: str) -> str:
    return 'runtime_api_key_' + provider


def enabled_setting(provider: str) -> str:
    return 'runtime_enabled_' + provider


def _read_fcc_env_key(var_names: List[str]) -> str:
    if 'PYTEST_CURRENT_TEST' in os.environ:
        return ''
    fcc_env = Path.home() / '.fcc' / '.env'
    if not fcc_env.exists():
        return ''
    try:
        for line in fcc_env.read_text(encoding='utf-8', errors='ignore').splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith('#') or '=' not in stripped:
                continue
            k, v = stripped.split('=', 1)
            if k.strip() in var_names and v.strip():
                return v.strip().strip('"').strip("'")
    except OSError:
        pass
    return ''


def resolve_api_key(provider: str, db: Any = None) -> str:
    if provider not in DIRECT_PROVIDERS:
        return ''
    _, key_var, _ = DIRECT_PROVIDERS[provider]
    env_candidates = [key_var]
    if provider == 'direct_nvidia':
        env_candidates.append('NVIDIA_NIM_API_KEY')
    for candidate in env_candidates:
        val = os.environ.get(candidate, '').strip()
        if val:
            return val
    if db is None and 'PYTEST_CURRENT_TEST' not in os.environ:
        try:
            from persistence import db_manager
            db = db_manager
        except Exception:
            db = None
    if db is not None:
        try:
            saved_key = (db.get_setting(api_key_setting(provider)) or '').strip()
            if saved_key:
                return saved_key
        except Exception:
            pass
    return _read_fcc_env_key(env_candidates)


def validate_model(model: Optional[str]) -> str:
    value = (model or '').strip()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}', value):
        raise ValueError('Enter a valid provider model ID (up to 200 characters).')
    if value in ('default', 'sonnet', 'opus', 'haiku', 'fable') or value.startswith('tier:'):
        raise ValueError('Direct API requires an explicit provider model ID, not a CLI alias or tier.')
    return value


def provider_for_model(model_id: Optional[str]) -> Optional[str]:
    if not model_id:
        return None
    cleaned = model_id.strip()
    if cleaned.startswith('nvidia_nim/'):
        return 'direct_nvidia'
    for prov_id, models in PROVIDER_MODELS.items():
        if any(m['id'] == cleaned for m in models):
            return prov_id
    if cleaned.startswith('claude-'):
        return 'direct_anthropic'
    if cleaned.startswith(('gpt-', 'o1-', 'o3-')):
        return 'direct_openai'
    return None


_RETIRED_NVIDIA_MODELS: Dict[str, str] = {
    'nvidia/nemotron-3-super-120b-a12b': 'nvidia/nemotron-3.5-super-vl-120b-a12b',
    'meta/llama-3.3-70b-instruct': 'nvidia/nemotron-3.5-lightning-30b-a3b',
    'deepseek-ai/deepseek-r1': 'nvidia/nemotron-3-ultra-550b-a55b',
    'qwen/qwen2.5-coder-32b-instruct': 'poolside/laguna-xs-2.1',
    'openai/gpt-oss-120b': 'nvidia/nemotron-3.5-super-vl-120b-a12b',
    'openai/gpt-oss-20b': 'nvidia/nemotron-3.5-super-vl-120b-a12b',
}


def resolve_model_for_provider(provider: str, raw_model: Optional[str], db: Any = None) -> str:
    saved_default = None
    if db is not None:
        try:
            saved_default = (db.get_setting(model_setting(provider)) or '').strip()
        except Exception:
            saved_default = None
    if provider == 'direct_nvidia' and saved_default in _RETIRED_NVIDIA_MODELS:
        saved_default = _RETIRED_NVIDIA_MODELS[saved_default]
    fallback_default = saved_default or DEFAULT_PROVIDER_MODEL.get(provider, '')
    candidate = (raw_model or 'default').strip()
    if candidate in ('default', 'sonnet', 'opus', 'haiku', 'fable') or candidate.startswith('tier:'):
        return validate_model(fallback_default)
    if provider == 'direct_nvidia':
        if candidate.startswith('nvidia_nim/'):
            candidate = candidate.removeprefix('nvidia_nim/')
        if candidate in _RETIRED_NVIDIA_MODELS:
            candidate = _RETIRED_NVIDIA_MODELS[candidate]
    owner = provider_for_model(candidate)
    if owner is not None and owner != provider:
        return validate_model(fallback_default)
    return validate_model(candidate)


def configuration(provider: str, db: Any = None):
    name, key_var, base_url = DIRECT_PROVIDERS[provider]
    key = resolve_api_key(provider, db=db)
    if not key:
        raise ValueError(f'{key_var} is not configured on the platform server.')
    return name, key, base_url


def configured_models(adapter, provider: str):
    db = adapter.services.database()
    model = db.get_setting(model_setting(provider)) or DEFAULT_PROVIDER_MODEL.get(provider)
    return ([{'model_id': validate_model(model), 'name': model, 'provider_id': provider}]
            if model else [])


def rates(provider: str, model: str = ''):
    from .direct_pricing import pricing
    return pricing(provider, model)['rates']
