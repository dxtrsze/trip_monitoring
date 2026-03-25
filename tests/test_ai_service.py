import pytest
import os
from ai_service import AIService

def test_ai_service_initialization():
    """Test that AIService initializes with OpenAI client"""
    api_key = os.environ.get("ZAI_API_KEY", "test_key")
    api_base = os.environ.get("ZAI_API_BASE", "https://api.z.ai/api/paas/v4")
    model = os.environ.get("ZAI_MODEL", "gpt-4")

    service = AIService(api_key=api_key, api_base=api_base, model=model)

    assert service.client is not None
    assert service.model == model
    assert service.api_base == api_base
