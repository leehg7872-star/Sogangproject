from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class LlmRequest:
    question: str
    mode: str
    tool_result: dict[str, Any]
    evidence: list[dict[str, str]] = field(default_factory=list)
    actions: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class LlmResponse:
    answer: str
    mode: str
    evidence: list[dict[str, str]]
    actions: list[dict[str, Any]] = field(default_factory=list)
    highlights: dict[str, Any] = field(default_factory=dict)
    adapter: str = "mock"

    def to_payload(self) -> dict[str, Any]:
        payload = {
            "answer": self.answer,
            "mode": self.mode,
            "evidence": self.evidence,
            "adapter": self.adapter,
        }
        if self.actions:
            payload["actions"] = self.actions
        if self.highlights:
            payload["highlights"] = self.highlights
        return payload


class LlmGateway(Protocol):
    def complete(self, request: LlmRequest) -> LlmResponse:
        ...


class MockAipGateway:
    """Local stand-in for the Palantir AIP Agent Studio contract."""

    def complete(self, request: LlmRequest) -> LlmResponse:
        return LlmResponse(
            answer=str(request.tool_result.get("answer", "")),
            mode=request.mode,
            evidence=request.evidence,
            actions=request.actions,
            highlights=dict(request.tool_result.get("highlights", {})),
            adapter="mock-aip",
        )


class PalantirAipGateway:
    """Configuration-only adapter for a future AIP Agent endpoint.

    In a Foundry/AIP deployment this class is the boundary to replace with
    Agent Studio tool invocation. Local runs intentionally fall back to mock
    behavior when no endpoint is configured.
    """

    def __init__(self) -> None:
        self.endpoint = os.getenv("ARGOS_AIP_AGENT_ENDPOINT", "")
        self.token = os.getenv("ARGOS_AIP_TOKEN", "")
        self.fallback = MockAipGateway()

    def complete(self, request: LlmRequest) -> LlmResponse:
        if not self.endpoint or not self.token:
            response = self.fallback.complete(request)
            response.adapter = "mock-aip-fallback"
            return response
        # Network calls are deliberately not made by the local MVP. The payload
        # shape below is the handoff contract for AIP Agent Studio integration.
        payload = {
            "question": request.question,
            "mode": request.mode,
            "toolResult": request.tool_result,
            "evidence": request.evidence,
            "actions": request.actions,
        }
        response = self.fallback.complete(request)
        response.adapter = "palantir-aip-contract"
        response.highlights["aipPayloadPreview"] = json.dumps(payload, ensure_ascii=False)[:1000]
        return response


def default_gateway() -> LlmGateway:
    return PalantirAipGateway()
