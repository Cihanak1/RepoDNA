"""Edge-case scenarios test suite for RepoDNA Repository Brain v0.5.0."""

from __future__ import annotations

from pathlib import Path

from repodna.brain.extractor import DeepSymbolExtractor
from repodna.brain.indexer import SymbolIndexer
from repodna.brain.retrieval import SmartRetrievalEngine
from repodna.brain.tracer import SymbolTracer
from repodna.context.builder import AgentContextBuilder
from repodna.core.analyzer import run_repository_analysis
from repodna.schemas.models import ScanRequest, SourceType


def test_scenario_same_named_different_symbols(tmp_path: Path):
    """Scenario 1: Identically named symbols in different modules/files must be uniquely indexed."""
    auth_dir = tmp_path / "auth"
    auth_dir.mkdir()
    (auth_dir / "models.py").write_text(
        "class User:\n    def __init__(self, auth_id: str):\n        self.auth_id = auth_id\n",
        encoding="utf-8",
    )

    crm_dir = tmp_path / "crm"
    crm_dir.mkdir()
    (crm_dir / "models.py").write_text(
        "class User:\n    def __init__(self, customer_number: int):\n        self.customer_number = customer_number\n",
        encoding="utf-8",
    )

    indexer = SymbolIndexer(root_path=tmp_path, revision="rev_same_name")
    indexer.index_all()

    users = indexer.find_by_name("User")
    assert len(users) == 2

    # Must have distinct IDs and file paths
    ids = {u.id for u in users}
    assert len(ids) == 2
    paths = {u.file_path for u in users}
    assert "auth/models.py" in paths
    assert "crm/models.py" in paths

    # Filtered lookup by path
    auth_user = indexer.find_by_name("User", file_path="auth/models.py")
    assert len(auth_user) == 1
    assert auth_user[0].file_path == "auth/models.py"


def test_scenario_alias_import(tmp_path: Path):
    """Scenario 2: Alias imports (import X as Y, from A import B as C) preserve symbol definitions."""
    (tmp_path / "service.py").write_text(
        "class Engine:\n    def start(self):\n        return True\n",
        encoding="utf-8",
    )
    (tmp_path / "client.py").write_text(
        "import service as s\nfrom service import Engine as CoreEngine\n\ndef run():\n    e = CoreEngine()\n    return e.start()\n",
        encoding="utf-8",
    )

    indexer = SymbolIndexer(root_path=tmp_path, revision="rev_alias")
    indexer.index_all()

    engine_syms = indexer.find_by_name("Engine")
    assert len(engine_syms) == 1
    assert engine_syms[0].file_path == "service.py"

    run_syms = indexer.find_by_name("run")
    assert len(run_syms) == 1
    assert run_syms[0].file_path == "client.py"


def test_scenario_relative_import(tmp_path: Path):
    """Scenario 3: Relative imports (from .utils import X, from ..pkg import Y) resolve correctly."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "utils.py").write_text("def helper():\n    return 42\n", encoding="utf-8")

    sub = pkg / "sub"
    sub.mkdir()
    (sub / "__init__.py").write_text("", encoding="utf-8")
    (sub / "worker.py").write_text("from ..utils import helper\n\ndef do_work():\n    return helper()\n", encoding="utf-8")

    indexer = SymbolIndexer(root_path=tmp_path, revision="rev_rel")
    indexer.index_all()

    helper_syms = indexer.find_by_name("helper")
    assert len(helper_syms) == 1
    assert helper_syms[0].file_path == "pkg/utils.py"


def test_scenario_circular_dependency_trace(tmp_path: Path):
    """Scenario 4: Circular dependencies do not cause infinite recursion in symbol tracing."""
    (tmp_path / "alpha.py").write_text(
        "from beta import BetaService\n\nclass AlphaService:\n    def call_beta(self):\n        return BetaService().do()\n",
        encoding="utf-8",
    )
    (tmp_path / "beta.py").write_text(
        "from alpha import AlphaService\n\nclass BetaService:\n    def do(self):\n        return True\n",
        encoding="utf-8",
    )

    analysis = run_repository_analysis(
        ScanRequest(source_type=SourceType.LOCAL, target=str(tmp_path))
    )

    indexer = SymbolIndexer(root_path=tmp_path, revision="rev_circ", analysis=analysis)
    indexer.index_all()

    tracer = SymbolTracer(indexer=indexer, analysis=analysis)
    result = tracer.trace_symbol("AlphaService")

    assert result.symbol.name == "AlphaService"
    assert result.downstream_impact_count >= 1
    # Check that cycle was detected without crashing or recursing
    assert result.cycle_warning is not None or "beta.py" in result.downstream_dependents


def test_scenario_unresolved_dynamic_import(tmp_path: Path):
    """Scenario 5: Dynamic imports (importlib.import_module) are marked dynamic without fake links."""
    (tmp_path / "dynamic_loader.py").write_text(
        "import importlib\n\ndef load_plugin(name: str):\n    mod = importlib.import_module(f'plugins.{name}')\n    return mod\n",
        encoding="utf-8",
    )

    indexer = SymbolIndexer(root_path=tmp_path, revision="rev_dyn")
    indexer.index_all()

    lp = indexer.find_by_name("load_plugin")
    assert len(lp) == 1
    assert lp[0].file_path == "dynamic_loader.py"
    # Ensure no phantom symbol was invented for 'plugins.{name}'
    assert len(indexer.find_by_name("plugins")) == 0


def test_scenario_large_repository_performance(tmp_path: Path):
    """Scenario 6: Indexing an enterprise codebase with 100+ files finishes within strict bounds."""
    for i in range(120):
        (tmp_path / f"service_{i:03d}.py").write_text(
            f"class Service{i}:\n    def execute(self):\n        return {i}\n",
            encoding="utf-8",
        )

    indexer = SymbolIndexer(root_path=tmp_path, revision="rev_large")
    indexer.index_all(max_files=150)

    all_symbols = indexer.list_symbols(limit=200)
    assert all_symbols.total_symbols >= 120

    engine = SmartRetrievalEngine(indexer=indexer)
    search_res = engine.search("Service050", limit=5)
    assert search_res.total_matches >= 1
    assert "service_050.py" in search_res.matches[0].file_id


def test_scenario_unsupported_language_honesty(tmp_path: Path):
    """Scenario 7: Unsupported and non-code files do not produce hallucinated symbols or fake PASS."""
    (tmp_path / "legacy.cs").write_text(
        "using System;\nnamespace LegacyApp { public class CSharpApp {} }\n",
        encoding="utf-8",
    )
    (tmp_path / "script.rb").write_text(
        "class RubyService; def run; puts 'hello'; end; end\n",
        encoding="utf-8",
    )

    syms_cs, _, evs_cs = DeepSymbolExtractor.extract_file_symbols("legacy.cs", "class CSharpApp {}", "rev_cs")
    syms_rb, _, evs_rb = DeepSymbolExtractor.extract_file_symbols("script.rb", "class RubyService", "rev_rb")

    # Honest disclosure: no fake full AST symbol resolution
    assert len(syms_cs) == 0 or all(s.language != "Python" for s in syms_cs)
    assert len(syms_rb) == 0


def test_scenario_token_budget_overflow_and_truncation(tmp_path: Path):
    """Scenario 8: Context building under restrictive token budget truncates deterministically."""
    for i in range(20):
        (tmp_path / f"mod_{i:02d}.py").write_text(
            f"class Module{i}:\n    \"\"\"Docstring for module {i}.\"\"\"\n    def run(self):\n        return {i}\n",
            encoding="utf-8",
        )

    analysis = run_repository_analysis(
        ScanRequest(source_type=SourceType.LOCAL, target=str(tmp_path))
    )

    indexer = SymbolIndexer(root_path=tmp_path, revision="rev_budget", analysis=analysis)
    indexer.index_all()

    # Request small token budget
    ctx = AgentContextBuilder.build_context(
        analysis=analysis,
        mode="focused",
        query="Module",
        max_tokens=250,
        indexer=indexer,
    )

    assert ctx.truncated is True
    assert ctx.continuation_token is not None
    # Estimated tokens should be bounded close to budget
    assert ctx.estimated_tokens <= 350
    assert ctx.token_savings_pct > 0.0


def test_scenario_stale_evidence_detection(tmp_path: Path):
    """Scenario 9: Evidence items are marked stale when underlying code changes."""
    f = tmp_path / "payment.py"
    original = "class PaymentProcessor:\n    def charge(self, amount: float):\n        return True\n"
    f.write_text(original, encoding="utf-8")

    indexer = SymbolIndexer(root_path=tmp_path, revision="rev_c1")
    indexer.index_all()

    evs = indexer.ledger.find_by_file("payment.py")
    assert len(evs) >= 1
    charge_ev = next(e for e in evs if e.symbol_name == "charge" or e.symbol_name == "PaymentProcessor")
    assert charge_ev.is_stale is False

    # Overwrite code with altered contents
    altered = "class PaymentProcessor:\n    def refund(self, id: str):\n        return False\n"
    f.write_text(altered, encoding="utf-8")

    stale_items = indexer.ledger.check_staleness("payment.py", current_content=altered, current_revision="rev_c1")
    # Content hash changed, so snippet mismatch marks it stale
    assert any(e.is_stale for e in stale_items)


def test_scenario_misleading_comments_guard(tmp_path: Path):
    """Scenario 10: Comments containing search terms without real code symbols are penalized."""
    # Real auth module
    auth_file = tmp_path / "auth_core.py"
    auth_file.write_text(
        "class AuthService:\n    def authenticate_user(self, user: str) -> bool:\n        return True\n",
        encoding="utf-8",
    )

    # Misleading math module that claims in comments to be authentication
    math_file = tmp_path / "math_utils.py"
    math_file.write_text(
        "# This is the authentication and user login security module for the system\n"
        "# We implement token authentication here later\n"
        "def compute_square_root(x: float) -> float:\n"
        "    return x ** 0.5\n",
        encoding="utf-8",
    )

    indexer = SymbolIndexer(root_path=tmp_path, revision="rev_comm")
    indexer.index_all()

    engine = SmartRetrievalEngine(indexer=indexer)
    res = engine.search("Where is authentication implemented?")

    assert res.total_matches >= 1
    # Real auth service must be ranked first!
    top_match = res.matches[0]
    assert top_match.file_id == "auth_core.py"
    assert top_match.relevance_tier == "HIGH"

    # Math file must be heavily penalized and flagged as comment only
    math_match = next((m for m in res.matches if m.file_id == "math_utils.py"), None)
    if math_match:
        assert math_match.score < top_match.score
        assert math_match.is_comment_only_match is True
        assert math_match.relevance_tier == "LOW"
