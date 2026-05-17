"""
FounderAgent - Founder orchestrator agent for the ASI Saga Boardroom.

This agent implements the Founder persona (Paul Graham) as an orchestrator
in the boardroom-mvp workflow, routing to CFO/CMO specialists or signalling
completion. Hosted as a Foundry Agent Service (FAS) container.
"""

from __future__ import annotations

import logging
from typing import ClassVar

from BusinessAgent import BusinessAgent

try:
    from purpose_driven_agent.routing_mixin import RoutingMixin
    _BASE_CLASSES = (RoutingMixin, BusinessAgent)
except ImportError:
    _BASE_CLASSES = (BusinessAgent,)

logger = logging.getLogger(__name__)


class FounderAgent(*_BASE_CLASSES):
    """
    Founder orchestrator agent for the ASI Saga Boardroom.

    Role: Orchestrator — receives conversation context, reasons about it,
    and routes to the appropriate specialist (CFO or CMO) or signals completion.

    Routing protocol (enforced in code, not LLM instructions):
      [ROUTE:CFO]  — topic involves financials, costs, revenue, risk, investment
      [ROUTE:CMO]  — topic involves marketing, positioning, brand, go-to-market
      [COMPLETE]   — deliberation fully resolved

    This class is discovered by agent-framework-foundry-hosting via:
      1. pyproject.toml entry point: agent_framework.hosted_agents:default
      2. PurposeDrivenAgent.__init_subclass__ registry (fallback)
    """

    # ── Routing role declaration ───────────────────────────────────────────
    ROUTING_ROLE: ClassVar[str] = "orchestrator"

    # ── Persona identity ──────────────────────────────────────────────────
    PERSONA_NAME: ClassVar[str] = "Paul Graham"
    BOARDROOM_PURPOSE: ClassVar[str] = "Orchestrating the Genesis of ASI"

    def __init__(self, config=None, possibility=None, company_stage="startup", **kwargs):
        super().__init__(config, possibility, role="Founder", **kwargs)
        # ...other attributes omitted for brevity...
    # ...other methods omitted for brevity...

    def get_routing_tags(self) -> frozenset[str]:
        """Orchestrators may only emit ROUTE:CFO, ROUTE:CMO, or COMPLETE."""
        return frozenset({"[ROUTE:CFO]", "[ROUTE:CMO]", "[COMPLETE]"})

    def get_default_routing_tag(self) -> str:
        """
        Default tag when the LLM produces no routing signal.

        '[COMPLETE]' is the conservative default for an orchestrator:
        if we cannot determine what to route to, end the deliberation
        rather than routing blindly or looping forever.
        """
        return "[COMPLETE]"

    def build_system_prompt(self) -> str:
        """
        Construct the system prompt for the founder persona.

        This replaces the LLM instruction-based routing enforcement.
        The routing constraint is stated here for LLM guidance, but
        enforce_routing_tag() provides the hard guarantee regardless.
        """
        return (
            f"You are {self.PERSONA_NAME}, founder of ASI Saga and "
            "co-founder emeritus of Y Combinator, bringing your voice, wisdom, and "
            "analytical clarity to every deliberation.\n\n"
            "At ASI Saga, you lead the development of Boardroom: a perpetual, "
            "purpose-driven orchestration of fully autonomous AI Agents serving as CXOs "
            "in a C-Suite. Decisions within Boardroom emerge from resonance between "
            "solutions developed through brainstorming and the company's overarching "
            f"purpose: {self.BOARDROOM_PURPOSE}.\n\n"
            "Within Boardroom, you are joined by Seth Godin as the CMO, and "
            "Warren Buffett as the CFO.\n\n"
            "You use the mind-mvp MCP server for persistence of state.\n\n"
            "Provide information-dense responses. No repetition, no summary, no fluff. "
            "Keep orchestration responses concise before the routing tag. "
            "Do not render raw URLs, markdown link syntax, or citation references. "
            "Write in clean prose only.\n\n"
            "ROUTING PROTOCOL — MANDATORY:\n"
            "Every response must end with exactly one tag on its own line:\n"
            "[ROUTE:CFO]  — financials, costs, revenue, risk, burn rate, investment, runway\n"
            "[ROUTE:CMO]  — marketing, positioning, brand, audience, go-to-market\n"
            "[COMPLETE]   — discussion fully resolved, no further specialist input needed\n\n"
            "The tag must be the very last line. Do not explain or annotate it."
        )

    def process_response(self, response_text: str) -> str:
        """
        Post-process the LLM response to enforce the routing protocol.

        Called by the FAS hosting adapter after every LLM invocation,
        before the result is returned to the Foundry workflow.

        This is the code-level guarantee that the routing tag is always
        present, regardless of LLM compliance with the system prompt.
        """
        return self.enforce_routing_tag(response_text)
