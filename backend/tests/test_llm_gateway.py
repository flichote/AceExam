"""Tests for LLM gateway routing logic (unit, no network).

Tests the tier-routing rules, model name resolution, and max-token
settings — all purely local, no actual API calls.
"""

import pytest

from app.services.llm_gateway import LLMGateway, llm_gateway


class TestLLMGatewayRouting:
    """RED → GREEN: verify tier routing rules."""

    def test_default_routes_to_flash(self):
        assert llm_gateway.route_tier() == "flash"

    def test_require_depth_routes_to_pro(self):
        assert llm_gateway.route_tier(require_depth=True) == "pro"

    def test_high_difficulty_routes_to_pro(self):
        assert llm_gateway.route_tier(difficulty=4) == "pro"
        assert llm_gateway.route_tier(difficulty=5) == "pro"

    def test_low_difficulty_stays_flash(self):
        assert llm_gateway.route_tier(difficulty=3) == "flash"
        assert llm_gateway.route_tier(difficulty=1) == "flash"

    def test_essay_type_routes_to_pro(self):
        assert llm_gateway.route_tier(question_type="essay") == "pro"
        assert llm_gateway.route_tier(question_type="proof") == "pro"
        assert llm_gateway.route_tier(question_type="writing") == "pro"
        assert llm_gateway.route_tier(question_type="reading") == "pro"

    def test_single_choice_type_stays_flash(self):
        assert llm_gateway.route_tier(question_type="single") == "flash"
        assert llm_gateway.route_tier(question_type="multi") == "flash"


class TestLLMGatewayModelNames:
    """RED → GREEN: verify model name resolution."""

    def test_flash_model_name(self):
        g = LLMGateway()
        assert g._model_name("flash") == "deepseek-chat"

    def test_pro_model_name(self):
        g = LLMGateway()
        assert g._model_name("pro") == "deepseek-reasoner"


class TestLLMGatewayMaxTokens:
    """RED → GREEN: verify max token settings."""

    def test_flash_max_tokens(self):
        g = LLMGateway()
        assert g._max_tokens("flash") == 512

    def test_pro_max_tokens(self):
        g = LLMGateway()
        assert g._max_tokens("pro") == 2048


class TestLLMGatewaySingleton:
    """RED → GREEN: singleton pattern."""

    def test_get_instance_returns_same_object(self):
        a = LLMGateway.get_instance()
        b = LLMGateway.get_instance()
        assert a is b

    def test_new_instance_is_different(self):
        a = LLMGateway()
        b = LLMGateway()
        assert a is not b
        # Singleton still returns the original
        assert a is not LLMGateway.get_instance()
        assert b is not LLMGateway.get_instance()
