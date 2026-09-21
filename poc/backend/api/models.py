"""
Model discovery and provider configuration API endpoints.
Provides dynamic list of available AI models for agent assignment.
"""

from fastapi import APIRouter
from typing import List, Optional
from pydantic import BaseModel

router = APIRouter()


class ModelOption(BaseModel):
    id: str
    name: str
    provider: str
    description: str
    context_window: int
    is_default: bool = False


class ModelCategory(BaseModel):
    provider: str
    models: List[ModelOption]


# Available model catalogue supported by platform runtimes
AVAILABLE_MODELS: List[ModelOption] = [
    ModelOption(
        id="default",
        name="Claude Code Default",
        provider="Anthropic",
        description="System configured default Claude model for CLI runner",
        context_window=200000,
        is_default=True
    ),
    ModelOption(
        id="claude-3-7-sonnet-20250219",
        name="Claude 3.7 Sonnet",
        provider="Anthropic",
        description="Hybrid reasoning model combining instant answers with step-by-step thinking",
        context_window=200000
    ),
    ModelOption(
        id="claude-3-5-sonnet-20241022",
        name="Claude 3.5 Sonnet",
        provider="Anthropic",
        description="High-intelligence flagship model optimized for software engineering and coding",
        context_window=200000
    ),
    ModelOption(
        id="claude-3-5-haiku-20241022",
        name="Claude 3.5 Haiku",
        provider="Anthropic",
        description="Ultra-fast, lightweight model ideal for quick subtasks and high throughput",
        context_window=200000
    ),
    ModelOption(
        id="claude-3-opus-20240229",
        name="Claude 3 Opus",
        provider="Anthropic",
        description="Deep contextual synthesis and high-level architectural planning",
        context_window=200000
    ),
    ModelOption(
        id="nvidia_nim/nvidia/nemotron-3-super-120b-a12b",
        name="Nemotron 3 Super 120B",
        provider="NVIDIA NIM",
        description="Enterprise grade open-weights model hosted on NVIDIA NIM infrastructure",
        context_window=128000
    ),
    ModelOption(
        id="nvidia_nim/meta/llama-3.3-70b-instruct",
        name="Llama 3.3 70B Instruct",
        provider="NVIDIA NIM",
        description="High-performance general instruction tuned model via NIM gateway",
        context_window=128000
    ),
]


@router.get("/", response_model=List[ModelOption])
@router.get("", response_model=List[ModelOption])
async def list_models():
    """List all available models discovered across supported providers."""
    return AVAILABLE_MODELS
