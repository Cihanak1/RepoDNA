"""Independent fidelity fixture tests for RepoDNA Symbol Resolution & Verification.

Strictly validates the 3-state resolution model (VERIFIED, CANDIDATE, UNRESOLVED)
across the 8 architectural scenarios required by v0.5.0 Phase 2:
1. Local shadowing
2. Namespace alias
3. Wildcard imports
4. Dynamic dispatch
5. Python package re-export
6. Same-name symbols across packages
7. TypeScript barrel exports
8. Python relative imports
"""

from __future__ import annotations

from pathlib import Path

from repodna.brain.indexer import SymbolIndexer
from repodna.brain.models import ReferenceKind, ResolutionStatus


def test_scenario_1_local_shadowing_preserves_unresolved(tmp_path: Path) -> None:
    """A parameter or local variable shadowing an imported name must NOT be verified as external symbol."""
    (tmp_path / "validator.py").write_text(
        "def validate_payload(data: dict) -> bool:\n    return len(data) > 0\n",
        encoding="utf-8",
    )
    (tmp_path / "handler.py").write_text(
        "from validator import validate_payload\n\n"
        "def process_request(validate_payload):\n"
        "    # validate_payload is a parameter shadowing the imported function!\n"
        "    return validate_payload()\n",
        encoding="utf-8",
    )

    indexer = SymbolIndexer(root_path=tmp_path, revision="rev_shadow")
    indexer.index_all()

    # The call to validate_payload inside process_request must be UNRESOLVED due to shadowing
    handler_refs = [
        r for r in indexer.get_references_in_file("handler.py")
        if r.reference_kind == ReferenceKind.CALL and r.symbol_name == "validate_payload"
    ]
    assert len(handler_refs) == 1
    call_ref = handler_refs[0]
    assert call_ref.resolution_status == ResolutionStatus.UNRESOLVED
    assert not call_ref.is_verified
    assert "shadows symbol" in call_ref.confidence_reason


def test_scenario_2_namespace_alias_resolution(tmp_path: Path) -> None:
    """Aliased imports (from X import Y as Z and import X as Y) resolve accurately as VERIFIED."""
    (tmp_path / "crypto.py").write_text(
        "def generate_token(salt: str) -> str:\n    return f'tok_{salt}'\n",
        encoding="utf-8",
    )
    (tmp_path / "auth.py").write_text(
        "from crypto import generate_token as gen_tok\n"
        "import crypto as crypt\n\n"
        "def login():\n"
        "    t1 = gen_tok('abc')\n"
        "    t2 = crypt.generate_token('def')\n"
        "    return t1, t2\n",
        encoding="utf-8",
    )

    indexer = SymbolIndexer(root_path=tmp_path, revision="rev_alias")
    indexer.index_all()

    auth_calls = [
        r for r in indexer.get_references_in_file("auth.py")
        if r.reference_kind == ReferenceKind.CALL
    ]
    assert len(auth_calls) >= 2

    # gen_tok call
    alias_call = next(r for r in auth_calls if r.symbol_name == "gen_tok")
    assert alias_call.resolution_status == ResolutionStatus.VERIFIED
    assert alias_call.is_verified
    assert alias_call.target_file_path == "crypto.py"
    assert "Statically verified aliased import" in alias_call.confidence_reason

    # crypt.generate_token call
    qual_call = next(r for r in auth_calls if r.symbol_name == "generate_token")
    assert qual_call.resolution_status == ResolutionStatus.VERIFIED
    assert qual_call.is_verified
    assert qual_call.target_file_path == "crypto.py"
    assert "Statically verified qualified call" in qual_call.confidence_reason


def test_scenario_3_wildcard_imports_produce_candidate_not_verified(tmp_path: Path) -> None:
    """Wildcard imports lack explicit static symbol proof; matches must be CANDIDATE, never VERIFIED."""
    (tmp_path / "helpers.py").write_text(
        "def sanitize_input(val: str) -> str:\n    return val.strip()\n\n"
        "def format_output(val: str) -> str:\n    return val.upper()\n",
        encoding="utf-8",
    )
    (tmp_path / "consumer.py").write_text(
        "from helpers import *\n\n"
        "def run():\n"
        "    a = sanitize_input('  test  ')\n"
        "    b = nonexistent_func()\n"
        "    return a, b\n",
        encoding="utf-8",
    )

    indexer = SymbolIndexer(root_path=tmp_path, revision="rev_wildcard")
    indexer.index_all()

    calls = [
        r for r in indexer.get_references_in_file("consumer.py")
        if r.reference_kind == ReferenceKind.CALL
    ]

    # sanitize_input is defined in helpers.py, but imported via wildcard (*)
    sanitize_call = next(r for r in calls if r.symbol_name == "sanitize_input")
    assert sanitize_call.resolution_status == ResolutionStatus.CANDIDATE
    assert not sanitize_call.is_verified
    assert sanitize_call.target_file_path == "helpers.py"
    assert "wildcard" in sanitize_call.confidence_reason.lower()

    # nonexistent_func is NOT defined in helpers.py
    missing_call = next(r for r in calls if r.symbol_name == "nonexistent_func")
    assert missing_call.resolution_status == ResolutionStatus.UNRESOLVED
    assert not missing_call.is_verified


def test_scenario_4_dynamic_dispatch_remains_unresolved(tmp_path: Path) -> None:
    """Dynamic runtime dispatch cannot be statically proven by AST and must remain UNRESOLVED."""
    (tmp_path / "actions.py").write_text(
        "class ActionService:\n"
        "    def do_create(self):\n"
        "        return 'created'\n"
        "    def do_delete(self):\n"
        "        return 'deleted'\n",
        encoding="utf-8",
    )
    (tmp_path / "dispatcher.py").write_text(
        "from actions import ActionService\n\n"
        "def dispatch(service: ActionService, action_name: str):\n"
        "    method = getattr(service, action_name)\n"
        "    return method()\n",
        encoding="utf-8",
    )

    indexer = SymbolIndexer(root_path=tmp_path, revision="rev_dispatch")
    indexer.index_all()

    # The call 'method()' is dynamic; neither do_create nor do_delete can be claimed as VERIFIED
    calls = [
        r for r in indexer.get_references_in_file("dispatcher.py")
        if r.reference_kind == ReferenceKind.CALL
    ]
    for call in calls:
        if call.symbol_name in ("do_create", "do_delete"):
            pytest_fail_msg = "Dynamic dispatch must not falsely verify concrete methods"
            raise AssertionError(pytest_fail_msg)

    # method() call cannot resolve to ActionService methods
    method_calls = [r for r in calls if r.symbol_name == "method"]
    if method_calls:
        assert method_calls[0].resolution_status == ResolutionStatus.UNRESOLVED


def test_scenario_5_python_package_reexport_resolution(tmp_path: Path) -> None:
    """Python package __init__.py re-exports resolve through to original definition as VERIFIED."""
    pkg = tmp_path / "billing"
    pkg.mkdir()
    (pkg / "invoice.py").write_text(
        "class InvoiceCalculator:\n"
        "    def compute_total(self, amount: float) -> float:\n"
        "        return amount * 1.20\n",
        encoding="utf-8",
    )
    (pkg / "__init__.py").write_text(
        "from .invoice import InvoiceCalculator\n",
        encoding="utf-8",
    )
    (tmp_path / "main.py").write_text(
        "from billing import InvoiceCalculator\n\n"
        "def main():\n"
        "    calc = InvoiceCalculator()\n"
        "    return calc.compute_total(100.0)\n",
        encoding="utf-8",
    )

    indexer = SymbolIndexer(root_path=tmp_path, revision="rev_reexport")
    indexer.index_all()

    # main.py imports InvoiceCalculator from billing
    main_imports = [
        r for r in indexer.get_references_in_file("main.py")
        if r.reference_kind == ReferenceKind.IMPORT and r.symbol_name == "InvoiceCalculator"
    ]
    assert len(main_imports) == 1
    imp = main_imports[0]
    assert imp.resolution_status == ResolutionStatus.VERIFIED
    assert imp.is_verified
    assert imp.target_file_path == "billing/invoice.py"

    # main.py call to InvoiceCalculator()
    main_calls = [
        r for r in indexer.get_references_in_file("main.py")
        if r.reference_kind == ReferenceKind.CALL and r.symbol_name == "InvoiceCalculator"
    ]
    assert len(main_calls) == 1
    assert main_calls[0].resolution_status == ResolutionStatus.VERIFIED
    assert main_calls[0].target_file_path == "billing/invoice.py"


def test_scenario_6_same_name_symbols_across_packages(tmp_path: Path) -> None:
    """Identically named symbols across packages resolve to the correct imported package."""
    crm = tmp_path / "crm"
    crm.mkdir()
    (crm / "models.py").write_text(
        "class Account:\n    def get_tier(self): return 'gold'\n",
        encoding="utf-8",
    )

    finance = tmp_path / "finance"
    finance.mkdir()
    (finance / "models.py").write_text(
        "class Account:\n    def get_balance(self): return 5000\n",
        encoding="utf-8",
    )

    (tmp_path / "audit.py").write_text(
        "from crm.models import Account as CrmAccount\n"
        "from finance.models import Account as FinAccount\n\n"
        "def run():\n"
        "    a = CrmAccount()\n"
        "    b = FinAccount()\n"
        "    c = UnimportedAccount()\n"
        "    return a, b, c\n",
        encoding="utf-8",
    )

    indexer = SymbolIndexer(root_path=tmp_path, revision="rev_same_name")
    indexer.index_all()

    calls = [
        r for r in indexer.get_references_in_file("audit.py")
        if r.reference_kind == ReferenceKind.CALL
    ]

    crm_call = next(r for r in calls if r.symbol_name == "CrmAccount")
    assert crm_call.resolution_status == ResolutionStatus.VERIFIED
    assert crm_call.target_file_path == "crm/models.py"

    fin_call = next(r for r in calls if r.symbol_name == "FinAccount")
    assert fin_call.resolution_status == ResolutionStatus.VERIFIED
    assert fin_call.target_file_path == "finance/models.py"

    unimported_call = next(r for r in calls if r.symbol_name == "UnimportedAccount")
    assert unimported_call.resolution_status == ResolutionStatus.UNRESOLVED
    assert not unimported_call.is_verified


def test_scenario_7_typescript_barrel_export(tmp_path: Path) -> None:
    """TypeScript barrel index.ts with export { X } from './sub' resolves to original sub module."""
    components = tmp_path / "components"
    components.mkdir()
    (components / "HealthCard.tsx").write_text(
        "export class HealthCard {\n"
        "    render() { return 'Card'; }\n"
        "}\n",
        encoding="utf-8",
    )
    (components / "index.ts").write_text(
        "export { HealthCard } from './HealthCard';\n",
        encoding="utf-8",
    )
    (tmp_path / "App.tsx").write_text(
        "import { HealthCard } from './components';\n\n"
        "export function App() {\n"
        "    const card = new HealthCard();\n"
        "    return card.render();\n"
        "}\n",
        encoding="utf-8",
    )

    indexer = SymbolIndexer(root_path=tmp_path, revision="rev_barrel")
    indexer.index_all()

    app_imports = [
        r for r in indexer.get_references_in_file("App.tsx")
        if r.reference_kind == ReferenceKind.IMPORT and r.symbol_name == "HealthCard"
    ]
    assert len(app_imports) == 1
    imp = app_imports[0]
    assert imp.resolution_status == ResolutionStatus.VERIFIED
    assert imp.is_verified
    assert imp.target_file_path == "components/HealthCard.tsx"


def test_scenario_8_python_relative_imports(tmp_path: Path) -> None:
    """Python relative imports across parent (..) and sibling (.) modules resolve accurately."""
    pkg = tmp_path / "core"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "base.py").write_text("class BaseEngine: pass\n", encoding="utf-8")

    sub = pkg / "sub"
    sub.mkdir()
    (sub / "__init__.py").write_text("", encoding="utf-8")
    (sub / "worker.py").write_text(
        "from ..base import BaseEngine\n"
        "from .helper import run_helper\n\n"
        "def do_work():\n"
        "    b = BaseEngine()\n"
        "    h = run_helper()\n"
        "    return b, h\n",
        encoding="utf-8",
    )
    (sub / "helper.py").write_text("def run_helper(): return 1\n", encoding="utf-8")

    indexer = SymbolIndexer(root_path=tmp_path, revision="rev_rel")
    indexer.index_all()

    worker_imports = [
        r for r in indexer.get_references_in_file("core/sub/worker.py")
        if r.reference_kind == ReferenceKind.IMPORT
    ]
    assert len(worker_imports) >= 2

    base_imp = next(r for r in worker_imports if r.symbol_name == "BaseEngine")
    assert base_imp.resolution_status == ResolutionStatus.VERIFIED
    assert base_imp.target_file_path == "core/base.py"

    helper_imp = next(r for r in worker_imports if r.symbol_name == "run_helper")
    assert helper_imp.resolution_status == ResolutionStatus.VERIFIED
    assert helper_imp.target_file_path == "core/sub/helper.py"
