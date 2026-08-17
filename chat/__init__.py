"""Member 2 — Agent, Ask ResolveOne, and AI Guardrails.

This module provides:
- investigate_exception(exception_id) → ProposedAction for automatic investigation
- handle_chat(request, access_context) → ChatResponse for EXPLAIN/QUERY/ACT intents
- AI guardrails: prompt injection detection, PII field blocking, citation validation
- LLM provider abstraction: OpenRouter/Groq or deterministic fake for testing
"""
