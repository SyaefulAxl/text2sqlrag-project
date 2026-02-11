"""
Cost Calculator Service
Tracks and calculates costs for embeddings and LLM queries.
"""

from typing import Dict, Any


class CostCalculator:
    """Service for calculating API costs."""

    # OpenAI Pricing (as of 2024)
    PRICING = {
        "embedding": {
            "text-embedding-3-small": 0.02 / 1_000_000,  # $0.02 per 1M tokens
            "text-embedding-3-large": 0.13 / 1_000_000,  # $0.13 per 1M tokens
        },
        "llm": {
            "gpt-4-turbo-preview": {
                "prompt": 0.01 / 1000,  # $0.01 per 1K prompt tokens
                "completion": 0.03 / 1000,  # $0.03 per 1K completion tokens
            },
            "gpt-4o": {
                "prompt": 0.005 / 1000,  # $0.005 per 1K prompt tokens
                "completion": 0.015 / 1000,  # $0.015 per 1K completion tokens
            },
            "gpt-3.5-turbo": {
                "prompt": 0.0005 / 1000,  # $0.0005 per 1K tokens
                "completion": 0.0015 / 1000,  # $0.0015 per 1K tokens
            },
        },
    }

    @staticmethod
    def calculate_embedding_cost(tokens: int, model: str = "text-embedding-3-small") -> float:
        """Calculate cost for embedding tokens."""
        rate = CostCalculator.PRICING["embedding"].get(model, 0.02 / 1_000_000)
        return tokens * rate

    @staticmethod
    def calculate_llm_cost(
        prompt_tokens: int,
        completion_tokens: int,
        model: str = "gpt-4-turbo-preview",
    ) -> float:
        """Calculate cost for LLM tokens."""
        model_pricing = CostCalculator.PRICING["llm"].get(model, {})
        prompt_rate = model_pricing.get("prompt", 0.01 / 1000)
        completion_rate = model_pricing.get("completion", 0.03 / 1000)
        return (prompt_tokens * prompt_rate) + (completion_tokens * completion_rate)

    @staticmethod
    def calculate_total_cost(
        usage: Dict[str, Any], llm_model: str = "gpt-4-turbo-preview"
    ) -> Dict[str, Any]:
        """Calculate total cost from usage data."""
        embedding_tokens = usage.get("embedding_tokens", 0)
        llm_prompt_tokens = usage.get("llm_prompt_tokens", 0)
        llm_completion_tokens = usage.get("llm_completion_tokens", 0)

        embedding_cost = CostCalculator.calculate_embedding_cost(embedding_tokens)
        llm_cost = CostCalculator.calculate_llm_cost(
            llm_prompt_tokens,
            llm_completion_tokens,
            llm_model,
        )
        total_cost = embedding_cost + llm_cost

        return {
            "embedding_cost": round(embedding_cost, 6),
            "llm_cost": round(llm_cost, 6),
            "total_cost": round(total_cost, 6),
            "formatted": {
                "embedding_cost": f"${embedding_cost:.6f}",
                "llm_cost": f"${llm_cost:.6f}",
                "total_cost": f"${total_cost:.6f}",
            },
        }

    @staticmethod
    def format_cost_display(cost_data: Dict[str, Any]) -> str:
        """Format cost data for display."""
        return (
            f"💰 **Cost Breakdown**\n"
            f"- Embedding: {cost_data['formatted']['embedding_cost']}\n"
            f"- LLM Query: {cost_data['formatted']['llm_cost']}\n"
            f"- **Total: {cost_data['formatted']['total_cost']}**"
        )
