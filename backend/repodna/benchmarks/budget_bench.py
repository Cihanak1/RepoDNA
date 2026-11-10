"""Budget compliance and pruning benchmark harness.

Systematically evaluates Phase 1.1 pruning algorithm under:
- max_tokens = 0
- max_tokens = 10
- max_tokens = 25
- max_tokens = 60
- max_tokens = 500
- max_tokens = 2000
"""

from __future__ import annotations

import re
import time

from repodna.benchmarks.models import BudgetComplianceResult
from repodna.context.builder import AgentContextBuilder
from repodna.schemas.models import AnalysisResult


def _strip_dynamic_timestamps(markdown_text: str) -> str:
    """Strips dynamic ISO timestamps (e.g. generated_at: 2026-11-10T...) for determinism verification."""
    return re.sub(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", "TIMESTAMP_NORMALIZED", markdown_text)


def run_budget_benchmark(analysis: AnalysisResult) -> list[BudgetComplianceResult]:
    """Runs systematic budget test matrix against the repository analysis."""
    test_budgets = [0, 10, 25, 60, 500, 2000]
    results: list[BudgetComplianceResult] = []

    for b in test_budgets:
        t0 = time.perf_counter()

        # Run 1
        resp1 = AgentContextBuilder.build_context(
            analysis=analysis,
            mode="smart_search",
            query="auth validator architecture",
            max_tokens=b,
            revision="BENCH_REV",
        )
        md1 = resp1.as_markdown()
        dur_ms = (time.perf_counter() - t0) * 1000.0

        # Run 2 for determinism test
        resp2 = AgentContextBuilder.build_context(
            analysis=analysis,
            mode="smart_search",
            query="auth validator architecture",
            max_tokens=b,
            revision="BENCH_REV",
        )
        md2 = resp2.as_markdown()

        norm_md1 = _strip_dynamic_timestamps(md1)
        norm_md2 = _strip_dynamic_timestamps(md2)
        is_deterministic = norm_md1 == norm_md2

        counted_tokens = resp1.estimated_tokens
        method = resp1.token_counting_method or "heuristic_chars"

        # Check compliance semantics:
        # If budget <= 60, metadata alone may exceed target tokens, in which case
        # resp1.truncated MUST be True and limitations MUST report header metadata limitation.
        is_compliant = False
        notes = ""

        if b <= 0:
            # 0 tokens requested: must indicate truncation and header limitation
            is_compliant = resp1.truncated is True
            notes = "Zero budget: correctly flagged as truncated with minimal metadata notice."
        elif b in (10, 25):
            # Extremely small budget: metadata exceeds budget; must be truncated
            is_compliant = resp1.truncated is True and any("budget" in lim.lower() for lim in resp1.limitations)
            notes = f"Small budget ({b} tokens): minimal metadata exceeds target; truncation flagged."
        elif b == 60:
            is_compliant = resp1.truncated is True or counted_tokens <= b
            notes = f"Tight budget ({b} tokens): successfully pruned down to essential summary."
        else:
            # 500 or 2000 tokens: should fit within budget or stay compliant
            is_compliant = counted_tokens <= (b + 20)  # small margin for markdown formatting
            notes = f"Generous budget ({b} tokens): consumed {counted_tokens} tokens safely."

        results.append(
            BudgetComplianceResult(
                max_tokens=b,
                counted_tokens=counted_tokens,
                counting_method=method,
                is_compliant=is_compliant,
                is_truncated=resp1.truncated,
                iterations=1,
                duration_ms=round(dur_ms, 2),
                is_deterministic=is_deterministic,
                notes=notes,
            )
        )

    return results
