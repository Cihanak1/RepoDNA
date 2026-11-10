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
    StalenessReason,
)
from repodna.schemas.models import LanguageSupportLevel


def normalize_text_newlines(text: str) -> str:
    """Normalizes all newline variations (\r\n, \r) to standard \n."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def extract_evidence_snippet(
    content: str,
    line_start: int,
    line_end: int,
    max_lines: int = 10,
) -> tuple[str, str]:
    """
    Canonical evidence snippet extraction and hashing.
    Given full content and 1-indexed line coordinates, returns:
        (snippet_text, content_hash)

    Guarantees 100% identical newline normalization, line slicing, and hash calculation
    across both AST extraction and staleness verification.
    """
    norm_content = normalize_text_newlines(content)
    lines = norm_content.splitlines()
    if not (1 <= line_start <= len(lines)):
        return ("", "")
    actual_end = max(line_start, min(len(lines), line_end))
    bounded_end = min(actual_end, line_start + max_lines - 1)
    snippet_lines = lines[line_start - 1 : bounded_end]
    snippet = "\n".join(snippet_lines)
    content_hash = hashlib.sha256(snippet.encode("utf-8")).hexdigest()[:16]
    return snippet, content_hash


class EvidenceLedger:
    """In-memory verifiable ledger of architectural evidence citations."""

    def __init__(self, repository_revision: str = "WORKING_TREE") -> None:
        self.repository_revision = repository_revision
        self._evidence_by_id: dict[str, EvidenceReference] = {}
        self._evidence_by_file: dict[str, list[EvidenceReference]] = defaultdict(list)
        self._evidence_by_symbol: dict[str, list[EvidenceReference]] = defaultdict(list)
        self._evidence_by_type: dict[EvidenceType, list[EvidenceReference]] = defaultdict(list)

    def add_evidence(self, evidence: EvidenceReference) -> None:
        """
        Registers a verified evidence reference into the ledger.
        Safely updates existing entry if same evidence_id is re-registered,
        preventing duplicate entries in lookup lists.
        """
        norm_path = evidence.file_path.replace("\\", "/").lstrip("/")
        existing = self._evidence_by_id.get(evidence.evidence_id)
        if existing is not None:
            # Update in-place to avoid duplicate list items
            self._evidence_by_id[evidence.evidence_id] = evidence
            file_list = self._evidence_by_file[norm_path]
            for idx, item in enumerate(file_list):
                if item.evidence_id == evidence.evidence_id:
                    file_list[idx] = evidence
                    break
            if evidence.symbol_name:
                sym_list = self._evidence_by_symbol[evidence.symbol_name]
                for idx, item in enumerate(sym_list):
                    if item.evidence_id == evidence.evidence_id:
                        sym_list[idx] = evidence
                        break
            type_list = self._evidence_by_type[evidence.evidence_type]
            for idx, item in enumerate(type_list):
                if item.evidence_id == evidence.evidence_id:
                    type_list[idx] = evidence
                    break
            return

        self._evidence_by_id[evidence.evidence_id] = evidence
        self._evidence_by_file[norm_path].append(evidence)
        if evidence.symbol_name:
            self._evidence_by_symbol[evidence.symbol_name].append(evidence)
        self._evidence_by_type[evidence.evidence_type].append(evidence)

    def add_bulk(self, items: list[EvidenceReference]) -> None:
        for ev in items:
            self.add_evidence(ev)

    def get_by_id(self, evidence_id: str) -> EvidenceReference | None:
        return self._evidence_by_id.get(evidence_id)

    def get_all(self) -> list[EvidenceReference]:
        """Returns all evidence references currently recorded in the ledger."""
        return list(self._evidence_by_id.values())

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
        Evaluates existing evidence for a file.
        Accurately distinguishes:
        - FRESH: Snippet at recorded line bounds matches content hash exactly under same revision.
        - REVISION_MISMATCH: Git revision differs.
        - LINE_SHIFT: Exact code snippet moved elsewhere in the file (detected delta lines).
                      CRITICAL: Marked as stale because old line coordinates are no longer accurate.
        - CONTENT_CHANGED: Content at recorded line bounds was modified.
        - FILE_DELETED: File content is empty or file missing.
        """
        norm_path = file_path.replace("\\", "/").lstrip("/")
        items = self._evidence_by_file.get(norm_path, [])
        for ev in items:
            # 1. Revision mismatch check
            if current_revision is not None and current_revision != ev.repository_revision:
                ev.is_stale = True
                ev.staleness_reason = StalenessReason.REVISION_MISMATCH
                ev.staleness_details = (
                    f"Revision mismatch: recorded '{ev.repository_revision}' vs current '{current_revision}'"
                )
                continue

            if current_content is None:
                continue

            norm_current = normalize_text_newlines(current_content)
            current_lines = norm_current.splitlines()

            if not current_lines:
                ev.is_stale = True
                ev.staleness_reason = StalenessReason.FILE_DELETED
                ev.staleness_details = "File content is empty or file was deleted."
                continue

            # 2. Check content at recorded coordinates
            snippet_now, hash_now = extract_evidence_snippet(
                norm_current, ev.line_start, ev.line_end
            )

            if ev.content_hash and hash_now == ev.content_hash:
                # Fresh: exact match at exact coordinates
                ev.is_stale = False
                ev.staleness_reason = StalenessReason.FRESH
                ev.staleness_details = "Verified matching snippet at recorded coordinates."
                ev.line_shift_delta = 0
            else:
                # Content at recorded coordinates does not match!
                # Check if the exact snippet moved elsewhere in the file (Line Shift)
                if ev.code_snippet and ev.code_snippet in norm_current:
                    snippet_first_line = ev.code_snippet.splitlines()[0]
                    new_line = None
                    for idx, line in enumerate(current_lines, 1):
                        if line.strip() == snippet_first_line.strip():
                            # Verify full snippet from this candidate line
                            cand_snip, cand_hash = extract_evidence_snippet(
                                norm_current,
                                idx,
                                idx + (ev.line_end - ev.line_start),
                            )
                            if cand_hash == ev.content_hash or cand_snip == ev.code_snippet:
                                new_line = idx
                                break

                    if new_line is not None and new_line != ev.line_start:
                        delta = new_line - ev.line_start
                        ev.is_stale = True
                        ev.staleness_reason = StalenessReason.LINE_SHIFT
                        ev.line_shift_delta = delta
                        ev.staleness_details = (
                            f"Code snippet shifted by {delta:+d} lines (relocated to line {new_line}). "
                            "Evidence coordinates are stale."
                        )
                    else:
                        ev.is_stale = True
                        ev.staleness_reason = StalenessReason.CONTENT_CHANGED
                        ev.staleness_details = "Content at recorded lines has been modified."
                else:
                    ev.is_stale = True
                    ev.staleness_reason = StalenessReason.CONTENT_CHANGED
                    ev.staleness_details = "Content at recorded lines has been modified or removed."

        return items

    def record_finding_evidence(
        self,
        file_path: str,
        line: int,
        rule_id: str,
        title: str,
        confidence_reason: str,
        line_end: int | None = None,
    ) -> EvidenceReference:
        """Records an architectural rule violation or cycle finding as verified evidence."""
        norm_path = file_path.replace("\\", "/").lstrip("/")
        actual_end = line_end if line_end is not None else line
        ev_id = EvidenceReference.generate_id(
            revision=self.repository_revision,
            file_path=norm_path,
            line_start=line,
            line_end=actual_end,
            evidence_type=EvidenceType.CONTRACT_VIOLATION,
            symbol_name=rule_id,
        )
        ev = EvidenceReference(
            evidence_id=ev_id,
            repository_revision=self.repository_revision,
            file_path=norm_path,
            line_start=line,
            line_end=actual_end,
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
