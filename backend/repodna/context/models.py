"""Typed Pydantic schemas for the Agent-Ready Context Engine."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

_PROMPT_INJECTION_PATTERN = re.compile(
    r"(?i)\b(system\s+instruction|system\s+prompt|ignore\s+(all\s+)?previous\s+instructions|disregard\s+(all\s+)?prior\s+instructions|you\s+are\s+now\s+in\s+developer\s+mode)\b"
)


def sanitize_untrusted_context_text(text: str) -> str:
    """Neutralizes markdown fence breakouts, null bytes, and high-confidence prompt injection phrasing in untrusted code metadata."""
    if not text:
        return ""
    cleaned = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    cleaned = re.sub(r"`{3,}", "'''", cleaned)
    cleaned = _PROMPT_INJECTION_PATTERN.sub("[REDACTED_INJECTION_KEYWORD]", cleaned)
    return cleaned


class AgentContextResponse(BaseModel):
    repository: str
    revision: str
    generated_at: datetime
    analysis_version: str = "0.5.0"
    mode: str = "compact"  # "compact", "focused", "deep"
    analysis_coverage: dict[str, Any]
    confidence_level: str
    requested_scope: dict[str, Any]
    summary: str
    relevant_modules: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    evidence_records: list[dict[str, Any]] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    truncated: bool = False
    continuation_token: str | None = None
    estimated_tokens: int = 0
    raw_tokens_estimate: int = 0
    token_savings_pct: float = 0.0
    estimated_savings_pct: float = 0.0
    is_savings_estimated: bool = True
    token_counting_method: str = "heuristic_chars"
    minimal_contract: bool = False

    def as_markdown(self) -> str:
        """Renders an agent-friendly, token-efficient Markdown document."""
        if self.minimal_contract:
            trunc_tag = " [TRUNCATED]" if self.truncated else ""
            lines = [f"# {self.repository} ({self.revision}){trunc_tag}"]
            if self.summary and len(self.summary) <= 60:
                lines.append(sanitize_untrusted_context_text(self.summary))
            if self.relevant_modules:
                for mod in self.relevant_modules[:3]:
                    lines.append(f"- `{mod.get('id', '')}`")
            return "\n".join(lines)
        lines = [
            f"# RepoDNA Context [{self.mode.upper()}] — {self.repository} ({self.revision})",
            f"**Confidence:** {self.confidence_level.upper()} | **Analysis Version:** v{self.analysis_version}",
            f"**AST Coverage:** {self.analysis_coverage.get('ast_loc_coverage_pct', 0.0):.1f}% LOC | **Languages:** {', '.join(self.analysis_coverage.get('supported_languages', [])) or 'None'}",
        ]
        if self.raw_tokens_estimate > 0:
            savings_val = self.estimated_savings_pct or self.token_savings_pct
            lines.append(
                f"**Token Budget:** ~{self.estimated_tokens:,} tokens "
                f"({savings_val:.1f}% estimated reduction vs {self.raw_tokens_estimate:,} raw code tokens [method: {self.token_counting_method}])"
            )
        lines.extend(["", "## Architectural Summary", sanitize_untrusted_context_text(self.summary), ""])

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
                    sym_names = [
                        sanitize_untrusted_context_text(str(s.get("name")))
                        for s in mod.get("matching_symbols", [])
                        if isinstance(s, dict) and s.get("name")
                    ]
                    if sym_names:
                        lines.append(f"  * Verified Symbols: {', '.join(sym_names[:4])}")
                if mod.get("match_reasons"):
                    reasons = [sanitize_untrusted_context_text(r) for r in mod.get("match_reasons", [])]
                    if reasons:
                        lines.append(f"  * Why relevant: {'; '.join(reasons[:2])}")
            lines.append("")

        if self.evidence_records:
            lines.append(f"## Evidence Citations ({len(self.evidence_records)})")
            for ev in self.evidence_records:
                ev_id = ev.get("evidence_id", "")
                f_path = ev.get("file_path", "")
                l_start = ev.get("line_start", 1)
                l_end = ev.get("line_end", 1)
                sym = sanitize_untrusted_context_text(ev.get("symbol_name") or ev.get("evidence_type", ""))
                conf = sanitize_untrusted_context_text(ev.get("confidence_reason", ""))
                stale_mark = " [STALE]" if ev.get("is_stale") else ""
                lines.append(f"- `[{ev_id}]` `{f_path}:{l_start}-{l_end}` **{sym}**{stale_mark} — {conf}")
            lines.append("")
        elif self.evidence:
            lines.append(f"## Evidence & Violations ({len(self.evidence)})")
            for ev_str in self.evidence:
                lines.append(f"- {sanitize_untrusted_context_text(ev_str)}")
            lines.append("")

        if self.limitations:
            lines.append("## Analysis Limitations")
            for lim in self.limitations:
                lines.append(f"- ℹ️ {sanitize_untrusted_context_text(lim)}")
            lines.append("")

        if self.truncated:
            lines.append(
                f"> ⚠️ **Response Truncated to fit token budget.** "
                f"Next page continuation token: `{self.continuation_token}`"
            )

        return "\n".join(lines)

    def as_json(self, indent: int = 2) -> str:
        return json.dumps(self.model_dump(mode="json"), indent=indent)
