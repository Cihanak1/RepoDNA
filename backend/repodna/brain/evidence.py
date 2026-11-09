"""Evidence Ledger for RepoDNA Repository Brain.

Maintains immutable, verified architectural evidence citations with Git revision provenance
and staleness detection.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict

from repodna.brain.models import (
    EvidenceLedgerResponse,
    EvidenceReference,
    EvidenceType,
)
from repodna.schemas.models import LanguageSupportLevel


class EvidenceLedger:
    """In-memory verifiable ledger of architectural evidence citations."""

    def __init__(self, repository_revision: str = "WORKING_TREE") -> None:
        self.repository_revision = repository_revision
        self._evidence_by_id: dict[str, EvidenceReference] = {}
        self._evidence_by_file: dict[str, list[EvidenceReference]] = defaultdict(list)
        self._evidence_by_symbol: dict[str, list[EvidenceReference]] = defaultdict(list)
        self._evidence_by_type: dict[EvidenceType, list[EvidenceReference]] = defaultdict(list)

    def add_evidence(self, evidence: EvidenceReference) -> None:
        """Registers a verified evidence reference into the ledger."""
        self._evidence_by_id[evidence.evidence_id] = evidence
        self._evidence_by_file[evidence.file_path].append(evidence)
        if evidence.symbol_name:
            self._evidence_by_symbol[evidence.symbol_name].append(evidence)
        self._evidence_by_type[evidence.evidence_type].append(evidence)

    def add_bulk(self, items: list[EvidenceReference]) -> None:
        for ev in items:
            self.add_evidence(ev)

    def get_by_id(self, evidence_id: str) -> EvidenceReference | None:
        return self._evidence_by_id.get(evidence_id)

    def find_by_file(
        self,
        file_path: str,
        line_start: int | None = None,
        line_end: int | None = None,
    ) -> list[EvidenceReference]:
        """Finds all evidence items recorded for a specific file within optional line bounds."""
        norm_path = file_path.replace("\\", "/").lstrip("/")
        items = self._evidence_by_file.get(norm_path, [])
        if line_start is None and line_end is None:
            return list(items)

        res: list[EvidenceReference] = []
        for ev in items:
            if line_start is not None and ev.line_end < line_start:
                continue
            if line_end is not None and ev.line_start > line_end:
                continue
            res.append(ev)
        return res

    def find_by_symbol(self, symbol_name: str) -> list[EvidenceReference]:
        return list(self._evidence_by_symbol.get(symbol_name, []))

    def find_by_type(self, evidence_type: EvidenceType) -> list[EvidenceReference]:
        return list(self._evidence_by_type.get(evidence_type, []))

    def check_staleness(
        self,
        file_path: str,
        current_content: str | None = None,
        current_revision: str | None = None,
    ) -> list[EvidenceReference]:
        """
        Evaluates existing evidence for a file. If current content or Git revision
        diverges from the recorded evidence hash or revision, marks items as stale.
        """
        norm_path = file_path.replace("\\", "/").lstrip("/")
        items = self._evidence_by_file.get(norm_path, [])
        for ev in items:
            if current_revision and current_revision != ev.repository_revision:
                ev.is_stale = True
            elif current_content is not None and ev.code_snippet:
                # Check if code snippet is still present at or near the recorded lines
                lines = current_content.splitlines()
                if 1 <= ev.line_start <= len(lines):
                    snippet_now = "\n".join(lines[ev.line_start - 1 : min(len(lines), ev.line_end)])
                    h_now = hashlib.sha256(snippet_now.encode("utf-8")).hexdigest()[:16]
                    if ev.content_hash and h_now != ev.content_hash and ev.code_snippet not in current_content:
                        ev.is_stale = True
                else:
                    ev.is_stale = True
        return items

    def record_finding_evidence(
        self,
        file_path: str,
        line: int,
        rule_id: str,
        title: str,
        confidence_reason: str,
    ) -> EvidenceReference:
        """Records an architectural rule violation or cycle finding as verified evidence."""
        ev_id = EvidenceReference.generate_id(
            revision=self.repository_revision,
            file_path=file_path,
            line_start=line,
            line_end=line,
            evidence_type=EvidenceType.CONTRACT_VIOLATION,
            symbol_name=rule_id,
        )
        ev = EvidenceReference(
            evidence_id=ev_id,
            repository_revision=self.repository_revision,
            file_path=file_path,
            line_start=line,
            line_end=line,
            evidence_type=EvidenceType.CONTRACT_VIOLATION,
            symbol_name=rule_id,
            support_level=LanguageSupportLevel.FULL_AST,
            confidence_reason=f"[{rule_id}] {title}: {confidence_reason}",
        )
        self.add_evidence(ev)
        return ev

    def to_response(self, limit: int = 50) -> EvidenceLedgerResponse:
        all_items = list(self._evidence_by_id.values())
        stale_count = sum(1 for e in all_items if e.is_stale)
        return EvidenceLedgerResponse(
            total_evidence=len(all_items),
            stale_count=stale_count,
            evidence_items=all_items[:limit],
            summary_text=(
                f"Evidence Ledger contains {len(all_items)} verified citation(s) "
                f"for revision '{self.repository_revision}' ({stale_count} stale)."
            ),
        )
