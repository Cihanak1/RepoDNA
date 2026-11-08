"""Typed Pydantic schemas for the Agent-Ready Context Engine."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AgentContextResponse(BaseModel):
    repository: str
    revision: str
    generated_at: datetime
    analysis_version: str = "0.3.0"
    mode: str = "compact"  # "compact", "focused", "deep"
    analysis_coverage: dict[str, Any]
    confidence_level: str
    requested_scope: dict[str, Any]
    summary: str
    relevant_modules: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    truncated: bool = False
    continuation_token: str | None = None
    estimated_tokens: int = 0

    def as_markdown(self) -> str:
        """Renders an agent-friendly, token-efficient Markdown document."""
        lines = [
            f"# RepoDNA Context [{self.mode.upper()}] — {self.repository} ({self.revision})",
            f"**Confidence:** {self.confidence_level.upper()} | **Analysis Version:** v{self.analysis_version}",
            f"**AST Coverage:** {self.analysis_coverage.get('ast_loc_coverage_pct', 0.0):.1f}% LOC | **Languages:** {', '.join(self.analysis_coverage.get('supported_languages', [])) or 'None'}",
            "",
            "## Architectural Summary",
            self.summary,
            "",
        ]

        if self.relevant_modules:
            lines.append(f"## Modules ({len(self.relevant_modules)})")
            for mod in self.relevant_modules:
                lines.append(
                    f"- `{mod.get('id', '')}` ({mod.get('language', '')}, {mod.get('lines_code', 0)} LOC) — "
                    f"Fan-In: {mod.get('fan_in', 0)}, Fan-Out: {mod.get('fan_out', 0)}, Instability: {mod.get('instability', 0.0):.2f}"
                )
                if mod.get("in_cycle"):
                    lines.append(f"  * ⚠️ Circular Dependency participant: {', '.join(mod.get('cycle_ids', []))}")
                if mod.get("is_hub"):
                    lines.append("  * 🏛️ Architectural Hub (high afferent coupling)")
                if mod.get("matching_symbols"):
                    sym_names = [str(s.get("name")) for s in mod.get("matching_symbols", []) if isinstance(s, dict) and s.get("name")]
                    if sym_names:
                        lines.append(f"  * Symbols: {', '.join(sym_names[:4])}")
            lines.append("")

        if self.evidence:
            lines.append(f"## Evidence & Violations ({len(self.evidence)})")
            for ev in self.evidence:
                lines.append(f"- {ev}")
            lines.append("")

        if self.limitations:
            lines.append("## Analysis Limitations")
            for lim in self.limitations:
                lines.append(f"- ℹ️ {lim}")
            lines.append("")

        if self.truncated:
            lines.append(
                f"> ⚠️ **Response Truncated to fit token/char budget.** "
                f"Next page continuation token: `{self.continuation_token}`"
            )

        return "\n".join(lines)

    def as_json(self, indent: int = 2) -> str:
        return json.dumps(self.model_dump(mode="json"), indent=indent)
