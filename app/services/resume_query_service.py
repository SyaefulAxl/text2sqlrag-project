"""
Resume Query Service - LLM-Powered Intent Detection

Parses user queries to determine intent:
- resume_search: Find candidates by skills/experience/name → Vector search
- sql_query: Statistics, counts, aggregations → Vanna AI
- chat: Greetings, help, general conversation → Return message
"""

import json
import logging
from typing import Optional, Dict, Any, Tuple

from openai import OpenAI

from app.config import settings

logger = logging.getLogger(__name__)

INTENT_SYSTEM_PROMPT = """You are a smart query router for a Resume Search System.
Analyze the user's query and determine the appropriate action.

Categories:
1. "resume_search" - Finding specific candidates by:
   - Skills (spinning, weaving, quality control)
   - Experience (10 years, senior)
   - Location (Tamil Nadu, India)
   - Education (B.Tech Textile)
   - Department (Spinning, Weaving, Dyeing)
   - Name (specific person search)
   
2. "sql_query" - Analytics and aggregations:
   - Counts ("how many resumes")
   - Statistics ("average experience")
   - Distributions ("resumes by department")
   - Top N ("top 5 experienced candidates")
   
3. "chat" - General conversation:
   - Greetings ("hello", "hi")
   - Help requests ("what can you do")
   - Unrelated topics

Return ONLY valid JSON with no extra text."""

INTENT_USER_PROMPT = """Analyze this query and return JSON:

Query: "{query}"

Return format:
{{
    "intent": "resume_search" | "sql_query" | "chat",
    "confidence": 0.0-1.0,
    "search_filters": {{
        "department": ["Spinning", ...] or null,
        "experience_min_years": number or null,
        "skills": ["skill1", ...] or null,
        "location": "location" or null,
        "name": "name" or null
    }},
    "sql_description": "description for SQL query" or null,
    "chat_response": "response for chat" or null
}}"""


class ResumeQueryService:
    """
    LLM-powered query understanding for resume search.
    
    Routes queries to:
    - Vector search (resume_search)
    - SQL generation (sql_query)
    - Direct response (chat)
    """

    def __init__(self):
        """Initialize query service."""
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = "gpt-4o-mini"

    def parse_query(self, query: str) -> Dict[str, Any]:
        """
        Parse user query to determine intent and extract filters.
        
        Args:
            query: User's natural language query
            
        Returns:
            Dict with intent, confidence, and relevant data
        """
        if not query or len(query.strip()) < 2:
            return {
                "intent": "chat",
                "confidence": 1.0,
                "chat_response": "Please enter a search query.",
            }

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": INTENT_SYSTEM_PROMPT},
                    {"role": "user", "content": INTENT_USER_PROMPT.format(query=query)},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=500,
                timeout=30.0,
            )

            content = (resp.choices[0].message.content or "").strip()
            result = json.loads(content)

            # Validate intent
            valid_intents = {"resume_search", "sql_query", "chat"}
            if result.get("intent") not in valid_intents:
                result["intent"] = "chat"
                result["chat_response"] = "I'm not sure how to handle that query."

            logger.info(f"Query intent: {result.get('intent')} (confidence: {result.get('confidence', 0):.2f})")
            return result

        except Exception as e:
            logger.error(f"Query parsing failed: {e}")
            return {
                "intent": "chat",
                "confidence": 0.5,
                "chat_response": "Sorry, I couldn't understand your query. Try searching for specific skills or experience.",
                "error": str(e),
            }

    def should_use_vector_search(self, parsed: Dict[str, Any]) -> bool:
        """Check if query should use vector search."""
        return parsed.get("intent") == "resume_search"

    def should_use_sql(self, parsed: Dict[str, Any]) -> bool:
        """Check if query should use SQL generation."""
        return parsed.get("intent") == "sql_query"

    def get_search_filters(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        """Extract search filters from parsed query."""
        filters = parsed.get("search_filters", {})
        return {k: v for k, v in filters.items() if v is not None} if filters else {}

    def get_sql_description(self, parsed: Dict[str, Any]) -> Optional[str]:
        """Get SQL description for Vanna AI."""
        return parsed.get("sql_description")

    def get_chat_response(self, parsed: Dict[str, Any]) -> str:
        """Get chat response for non-search queries."""
        return parsed.get("chat_response", "I can help you search for candidates. Try asking about specific skills or experience.")


# Singleton instance
_query_service = None

def get_query_service() -> ResumeQueryService:
    """Get singleton instance of ResumeQueryService."""
    global _query_service
    if _query_service is None:
        _query_service = ResumeQueryService()
    return _query_service
