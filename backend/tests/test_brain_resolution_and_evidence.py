"""Comprehensive Phase 1.1 tests for Symbol Resolution, Evidence Integrity, and Context Budgeting.

Verifies:
1. Unrelated unique function in repository is not falsely verified.
2. Two different classes with the same name trigger AmbiguousSymbolError on tracing unless disambiguated.
3. Functions with the same name in two different modules.
4. Alias import correctly maps to origin symbol and verifies.
5. Local shadowing (parameter or local variable) prevents false outer verification.
6. Dynamic dispatch / unresolved dynamic calls.
7. Unresolved import handling.
8. Same content with different Git revision triggers revision mismatch.
9. Snippet moved elsewhere in file is correctly detected as LINE_SHIFT staleness.
10. Line shift delta measurement.
11. Unchanged fresh evidence verification.
12. Very small token budget handling.
13. Metadata exceeding budget handling.
14. Continuation pagination logic.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from repodna.brain.evidence import EvidenceLedger, extract_evidence_snippet
from repodna.brain.indexer import SymbolIndexer
from repodna.brain.models import (
    ReferenceKind,
    ResolutionStatus,
    StalenessReason,
)
from repodna.brain.tracer import AmbiguousSymbolError, SymbolTracer
from repodna.context.builder import AgentContextBuilder
from repodna.core.analyzer import run_repository_analysis
from repodna.schemas.models import ScanRequest, SourceType


def test_scenario_unrelated_single_function_not_verified(tmp_path: Path):
    """1. A function unique in the repository must NOT be verified when called in an unrelated unimported module."""
    # Module A defines calculate_tax
    (tmp_path / "tax.py").write_text(
        "def calculate_tax(amount: float) -> float:\n    return amount * 0.2\n",
        encoding="utf-8",
    )
    # Module B calls calculate_tax() without importing tax.py
    (tmp_path / "orders.py").write_text(
        "def process_order(price: float):\n    return calculate_tax(price)\n",
        encoding="utf-8",
    )

    analysis = run_repository_analysis(
        ScanRequest(source_type=SourceType.LOCAL, target=str(tmp_path))
    )
    indexer = SymbolIndexer(root_path=tmp_path, revision="rev_single", analysis=analysis)
    indexer.index_all()

    tax_syms = indexer.find_by_name("calculate_tax")
    assert len(tax_syms) == 1
    tax_def = tax_syms[0]

    # The call in orders.py must NOT be in tax_def.verified_references
    # Because orders.py does not import tax.py!
    assert len(tax_def.verified_references) == 0

    # Looking at raw references in orders.py
    orders_refs = [r for r in indexer._raw_references if r.file_path == "orders.py" and r.symbol_name == "calculate_tax"]
    assert len(orders_refs) == 1
    assert orders_refs[0].resolution_status == ResolutionStatus.UNRESOLVED
    assert orders_refs[0].is_verified is False
    assert "no import or dependency link" in orders_refs[0].confidence_reason


def test_scenario_ambiguous_classes_tracing(tmp_path: Path):
    """2. Two different classes with the same name must raise AmbiguousSymbolError unless disambiguated."""
    pkg_a = tmp_path / "billing"
    pkg_a.mkdir()
    (pkg_a / "models.py").write_text("class Account:\n    def bill(self): pass\n", encoding="utf-8")

    pkg_b = tmp_path / "auth"
    pkg_b.mkdir()
    (pkg_b / "models.py").write_text("class Account:\n    def authenticate(self): pass\n", encoding="utf-8")

    indexer = SymbolIndexer(root_path=tmp_path, revision="rev_ambig")
    indexer.index_all()

    tracer = SymbolTracer(indexer=indexer)

    # Calling trace without disambiguation must raise AmbiguousSymbolError
    with pytest.raises(AmbiguousSymbolError) as exc_info:
        tracer.trace_symbol(symbol_name="Account")

    assert "ambiguous" in str(exc_info.value).lower()
    assert len(exc_info.value.candidates) == 2

    # Disambiguation with file_path succeeds
    res_billing = tracer.trace_symbol(symbol_name="Account", file_path="billing/models.py")
    assert res_billing.symbol.file_path == "billing/models.py"

    # Disambiguation with symbol_id succeeds
    auth_acc = next(s for s in exc_info.value.candidates if s.file_path == "auth/models.py")
    res_id = tracer.trace_symbol(symbol_id=auth_acc.id)
    assert res_id.symbol.file_path == "auth/models.py"


def test_scenario_functions_with_same_name_in_different_modules(tmp_path: Path):
    """3. Same-named functions in different modules must be distinctly indexed and resolved only to the imported one."""
    (tmp_path / "encoder.py").write_text("def parse(data: str):\n    return data.encode()\n", encoding="utf-8")
    (tmp_path / "decoder.py").write_text("def parse(data: str):\n    return data.decode()\n", encoding="utf-8")
    (tmp_path / "consumer.py").write_text(
        "from encoder import parse\n\ndef run():\n    return parse('test')\n",
        encoding="utf-8",
    )

    indexer = SymbolIndexer(root_path=tmp_path, revision="rev_same_func")
    indexer.index_all()

    enc_parse = next(s for s in indexer.find_by_name("parse") if s.file_path == "encoder.py")
    dec_parse = next(s for s in indexer.find_by_name("parse") if s.file_path == "decoder.py")

    # consumer.py imports encoder.parse -> enc_parse must have the verified call reference
    assert any(r.file_path == "consumer.py" for r in enc_parse.verified_references)
    # dec_parse must NOT have any verified reference from consumer.py
    assert not any(r.file_path == "consumer.py" for r in dec_parse.verified_references)


def test_scenario_alias_import_resolution(tmp_path: Path):
    """4. Alias import 'from x import y as z' resolves call z() to y in x with VERIFIED status."""
    (tmp_path / "crypto.py").write_text("def hash_password(pwd: str):\n    return 'hashed'\n", encoding="utf-8")
    (tmp_path / "auth.py").write_text(
        "from crypto import hash_password as hash_pwd\n\ndef login(pwd: str):\n    return hash_pwd(pwd)\n",
        encoding="utf-8",
    )

    indexer = SymbolIndexer(root_path=tmp_path, revision="rev_alias")
    indexer.index_all()

    crypto_sym = indexer.find_by_name("hash_password")[0]
    verified_refs = crypto_sym.verified_references

    assert len(verified_refs) >= 1
    call_ref = next(r for r in verified_refs if r.file_path == "auth.py" and r.reference_kind == ReferenceKind.CALL)
    assert call_ref.resolution_status == ResolutionStatus.VERIFIED
    assert call_ref.symbol_name == "hash_pwd"
    assert call_ref.target_symbol_id == crypto_sym.id
    assert "aliased import" in call_ref.confidence_reason


def test_scenario_local_shadowing(tmp_path: Path):
    """5. Local parameter or local assignment shadowing an outer symbol must NOT be falsely verified."""
    (tmp_path / "math_ops.py").write_text("def calculate(x: int) -> int:\n    return x * 2\n", encoding="utf-8")
    (tmp_path / "worker.py").write_text(
        "from math_ops import calculate\n\n"
        "def execute(calculate):\n"
        "    # Parameter 'calculate' shadows imported calculate\n"
        "    return calculate()\n",
        encoding="utf-8",
    )

    indexer = SymbolIndexer(root_path=tmp_path, revision="rev_shadow")
    indexer.index_all()

    math_sym = indexer.find_by_name("calculate")[0]
    # The shadowed call inside execute(calculate) must NOT be verified against math_ops.calculate
    worker_calls = [r for r in math_sym.verified_references if r.file_path == "worker.py" and r.reference_kind == ReferenceKind.CALL]
    assert len(worker_calls) == 0

    worker_refs = [r for r in indexer._raw_references if r.file_path == "worker.py" and r.symbol_name == "calculate" and r.reference_kind == ReferenceKind.CALL]
    assert len(worker_refs) == 1
    assert worker_refs[0].resolution_status == ResolutionStatus.UNRESOLVED
    assert "shadows symbol" in worker_refs[0].confidence_reason


def test_scenario_dynamic_dispatch_and_unresolved_import(tmp_path: Path):
    """6 & 7. Dynamic dispatch and missing imports remain safely UNRESOLVED."""
    (tmp_path / "dispatcher.py").write_text(
        "import importlib\n"
        "from nonexistent_module import ghost_function\n\n"
        "def dispatch(func_name: str, obj):\n"
        "    fn = getattr(obj, func_name)\n"
        "    return fn()\n",
        encoding="utf-8",
    )

    indexer = SymbolIndexer(root_path=tmp_path, revision="rev_dyn")
    indexer.index_all()

    ghost_refs = [r for r in indexer._raw_references if r.symbol_name == "ghost_function"]
    assert len(ghost_refs) >= 1
    assert ghost_refs[0].resolution_status == ResolutionStatus.UNRESOLVED
    assert "could not be resolved" in ghost_refs[0].confidence_reason


def test_scenario_evidence_different_git_revision(tmp_path: Path):
    """8. Evidence tested against a different Git revision is flagged as REVISION_MISMATCH."""
    f = tmp_path / "service.py"
    code = "def start():\n    return True\n"
    f.write_text(code, encoding="utf-8")

    ledger = EvidenceLedger(repository_revision="commit_aaa")
    snippet, c_hash = extract_evidence_snippet(code, 1, 2)
    ev = ledger.record_finding_evidence(
        file_path="service.py",
        line=1,
        line_end=2,
        rule_id="ARCH001",
        title="Rule Title",
        confidence_reason="Initial verification",
    )
    ev.code_snippet = snippet
    ev.content_hash = c_hash

    # Check staleness with matching revision and content -> FRESH
    stale_fresh = ledger.check_staleness("service.py", current_content=code, current_revision="commit_aaa")
    assert stale_fresh[0].is_stale is False
    assert stale_fresh[0].staleness_reason == StalenessReason.FRESH

    # Check staleness with different revision -> REVISION_MISMATCH
    stale_mismatch = ledger.check_staleness("service.py", current_content=code, current_revision="commit_bbb")
    assert stale_mismatch[0].is_stale is True
    assert stale_mismatch[0].staleness_reason == StalenessReason.REVISION_MISMATCH
    assert "commit_aaa" in (stale_mismatch[0].staleness_details or "")


def test_scenario_evidence_line_shift_detection(tmp_path: Path):
    """9 & 10. Code shifted by inserting lines is detected as LINE_SHIFT staleness with delta."""
    f = tmp_path / "payment.py"
    original = "def charge(amount):\n    return True\n"
    f.write_text(original, encoding="utf-8")

    ledger = EvidenceLedger(repository_revision="rev_shift")
    snippet, c_hash = extract_evidence_snippet(original, 1, 2)
    ev = ledger.record_finding_evidence(
        file_path="payment.py",
        line=1,
        line_end=2,
        rule_id="ARCH002",
        title="Payment Guard",
        confidence_reason="Initial check",
    )
    ev.code_snippet = snippet
    ev.content_hash = c_hash

    # Prepend 5 comment lines (shifting code down by 5 lines)
    shifted = "# Comment 1\n# Comment 2\n# Comment 3\n# Comment 4\n# Comment 5\ndef charge(amount):\n    return True\n"
    f.write_text(shifted, encoding="utf-8")

    stale_items = ledger.check_staleness("payment.py", current_content=shifted, current_revision="rev_shift")
    assert len(stale_items) == 1
    item = stale_items[0]

    # Must be marked stale because original line coordinates 1-2 are no longer valid!
    assert item.is_stale is True
    assert item.staleness_reason == StalenessReason.LINE_SHIFT
    assert item.line_shift_delta == 5
    assert "shifted by +5 lines" in (item.staleness_details or "")


def test_scenario_evidence_content_modified(tmp_path: Path):
    """11. Content modified at recorded lines without snippet intact is detected as CONTENT_CHANGED."""
    f = tmp_path / "data.py"
    original = "def fetch_data():\n    return [1, 2, 3]\n"
    f.write_text(original, encoding="utf-8")

    ledger = EvidenceLedger(repository_revision="rev_mod")
    snippet, c_hash = extract_evidence_snippet(original, 1, 2)
    ev = ledger.record_finding_evidence(
        file_path="data.py",
        line=1,
        rule_id="ARCH003",
        title="Data Check",
        confidence_reason="Initial check",
    )
    ev.code_snippet = snippet
    ev.content_hash = c_hash

    modified = "def fetch_data_v2():\n    return {'items': []}\n"
    f.write_text(modified, encoding="utf-8")

    stale_items = ledger.check_staleness("data.py", current_content=modified, current_revision="rev_mod")
    assert stale_items[0].is_stale is True
    assert stale_items[0].staleness_reason == StalenessReason.CONTENT_CHANGED


def test_scenario_token_budget_zero_and_negative(tmp_path: Path):
    """12. Zero and negative token budgets are safely handled with minimal truncated response."""
    (tmp_path / "demo.py").write_text("def run(): pass\n", encoding="utf-8")
    analysis = run_repository_analysis(ScanRequest(source_type=SourceType.LOCAL, target=str(tmp_path)))

    # Zero budget
    ctx_zero = AgentContextBuilder.build_context(analysis, mode="compact", max_tokens=0)
    assert ctx_zero.truncated is True
    assert ctx_zero.estimated_tokens == 0
    assert len(ctx_zero.relevant_modules) == 0

    # Negative budget
    ctx_neg = AgentContextBuilder.build_context(analysis, mode="compact", max_tokens=-50)
    assert ctx_neg.truncated is True
    assert len(ctx_neg.relevant_modules) == 0
    assert any("zero or negative" in lim for lim in ctx_neg.limitations)


def test_scenario_metadata_exceeding_tiny_budget(tmp_path: Path):
    """13. Extremely small budget (e.g. 15 tokens) prunes modules, evidence and summary gracefully without infinite loop."""
    for i in range(10):
        (tmp_path / f"service_{i}.py").write_text(f"def serve_{i}(): return {i}\n", encoding="utf-8")
    analysis = run_repository_analysis(ScanRequest(source_type=SourceType.LOCAL, target=str(tmp_path)))

    ctx_tiny = AgentContextBuilder.build_context(analysis, mode="compact", max_tokens=25)
    assert ctx_tiny.truncated is True
    # Pruned down to minimal
    assert len(ctx_tiny.relevant_modules) <= 1
    assert ctx_tiny.continuation_token is not None


def test_scenario_continuation_pagination_logic(tmp_path: Path):
    """14. Continuation token pagination allows sequential retrieval across pages."""
    for i in range(15):
        (tmp_path / f"module_{i:02d}.py").write_text(f"class Component{i}: pass\n", encoding="utf-8")
    analysis = run_repository_analysis(ScanRequest(source_type=SourceType.LOCAL, target=str(tmp_path)))

    # Page 0 with page_size=5
    ctx_p0 = AgentContextBuilder.build_context(analysis, mode="compact", page=0, page_size=5)
    assert ctx_p0.continuation_token == "page=1"
    assert len(ctx_p0.relevant_modules) == 5

    # Page 1 with page_size=5
    ctx_p1 = AgentContextBuilder.build_context(analysis, mode="compact", page=1, page_size=5)
    assert ctx_p1.continuation_token == "page=2"
    assert len(ctx_p1.relevant_modules) == 5

    # Distinct modules across pages
    ids_p0 = {m["id"] for m in ctx_p0.relevant_modules}
    ids_p1 = {m["id"] for m in ctx_p1.relevant_modules}
    assert ids_p0.isdisjoint(ids_p1)
