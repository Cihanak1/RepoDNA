"""Unit and integration tests for RepoDNA Repository Brain.

Tests Symbol Intelligence, Smart Retrieval, Evidence Ledger, and Tracer.
"""

from __future__ import annotations

from pathlib import Path

from repodna.brain.evidence import EvidenceLedger
from repodna.brain.extractor import DeepSymbolExtractor
from repodna.brain.indexer import SymbolIndexer
from repodna.brain.models import (
    EvidenceType,
    SymbolKind,
)
from repodna.brain.retrieval import (
    SmartRetrievalEngine,
    _classify_query_intent,
    _split_identifier_tokens,
)


def test_split_identifier_tokens():
    assert _split_identifier_tokens("requestValidation") == ["request", "validation"]
    assert _split_identifier_tokens("AuthService_v2") == ["auth", "service", "v2"]
    assert _split_identifier_tokens("get_user_by_id") == ["get", "user", "by", "id"]
    assert _split_identifier_tokens("XMLParser") == ["xml", "parser"]


def test_query_intent_classification():
    assert _classify_query_intent("Where is authentication implemented?") == "where_is"
    assert _classify_query_intent("Which modules depend on this service?") == "dependency_trace"
    assert _classify_query_intent("What could be affected by changing this function?") == "impact_analysis"
    assert _classify_query_intent("find class AuthService") == "find_symbol"
    assert _classify_query_intent("calculate cyclomatic complexity") == "general_search"


def test_deep_symbol_extractor_python():
    code = '''"""Module docstring."""

class AuthService:
    """Service for user authentication."""
    def __init__(self, secret: str):
        self.secret = secret

    def authenticate_user(self, username: str, token: str) -> bool:
        """Verifies authentication token."""
        return token == self.secret

def create_auth_service() -> AuthService:
    return AuthService("secret_123")
'''
    syms, refs, evs = DeepSymbolExtractor.extract_file_symbols(
        file_path="auth/service.py",
        content=code,
        revision="rev_test_1",
    )

    names = {s.name for s in syms}
    assert "AuthService" in names
    assert "__init__" in names
    assert "authenticate_user" in names
    assert "create_auth_service" in names

    auth_cls = next(s for s in syms if s.name == "AuthService")
    assert auth_cls.kind == SymbolKind.CLASS
    assert auth_cls.container_name is None
    assert auth_cls.docstring is not None
    assert "authentication" in auth_cls.docstring.lower()

    auth_method = next(s for s in syms if s.name == "authenticate_user")
    assert auth_method.kind == SymbolKind.METHOD
    assert auth_method.container_name == "AuthService"
    assert auth_method.signature is not None
    assert "authenticate_user" in auth_method.signature

    fn_standalone = next(s for s in syms if s.name == "create_auth_service")
    assert fn_standalone.kind == SymbolKind.FUNCTION
    assert fn_standalone.container_name is None

    # Verify Evidence Ledger items
    assert len(evs) >= 4
    for ev in evs:
        assert ev.evidence_id.startswith("ev_")
        assert ev.repository_revision == "rev_test_1"
        assert ev.file_path == "auth/service.py"
        assert ev.evidence_type == EvidenceType.SYMBOL_DEFINITION


def test_deep_symbol_extractor_typescript():
    ts_code = """
export interface TokenPayload {
    id: string;
    role: string;
}

export type TokenResult = TokenPayload | null;

export class JwtValidator {
    private secret: string;
    constructor(secret: string) {
        this.secret = secret;
    }

    public validateToken(rawToken: string): TokenResult {
        return { id: "u1", role: "admin" };
    }
}

export function parseJwt(header: string): TokenResult {
    const val = new JwtValidator("s");
    return val.validateToken(header);
}
"""
    syms, refs, evs = DeepSymbolExtractor.extract_file_symbols(
        file_path="src/jwt.ts",
        content=ts_code,
        revision="rev_test_ts",
    )

    names = {s.name for s in syms}
    assert "TokenPayload" in names
    assert "TokenResult" in names
    assert "JwtValidator" in names
    assert "validateToken" in names
    assert "parseJwt" in names

    iface = next(s for s in syms if s.name == "TokenPayload")
    assert iface.kind == SymbolKind.INTERFACE

    type_sym = next(s for s in syms if s.name == "TokenResult")
    assert type_sym.kind == SymbolKind.TYPE

    method_sym = next(s for s in syms if s.name == "validateToken")
    assert method_sym.kind == SymbolKind.METHOD
    assert method_sym.container_name == "JwtValidator"


def test_evidence_ledger_management_and_staleness():
    ledger = EvidenceLedger(repository_revision="commit_100")

    content_v1 = "def authenticate():\n    return True\n"
    syms, refs, evs = DeepSymbolExtractor.extract_file_symbols(
        file_path="core/auth.py",
        content=content_v1,
        revision="commit_100",
    )
    ledger.add_bulk(evs)

    assert len(ledger.find_by_file("core/auth.py")) >= 1
    assert len(ledger.find_by_symbol("authenticate")) >= 1

    ev_item = ledger.find_by_symbol("authenticate")[0]
    assert ev_item.is_stale is False

    # Check freshness against identical content
    ledger.check_staleness("core/auth.py", current_content=content_v1, current_revision="commit_100")
    assert ev_item.is_stale is False

    # Check staleness on content change
    content_v2 = "def different_function():\n    return False\n"
    ledger.check_staleness("core/auth.py", current_content=content_v2, current_revision="commit_100")
    assert ev_item.is_stale is True

    # Check staleness on revision mismatch
    ev_item2 = ledger.find_by_symbol("authenticate")[0]
    ledger.check_staleness("core/auth.py", current_revision="commit_200")
    assert ev_item2.is_stale is True


def test_symbol_indexer_and_cross_reference_resolution(tmp_path: Path):
    auth_file = tmp_path / "auth.py"
    auth_file.write_text(
        "class AuthService:\n    def login(self, u: str) -> bool:\n        return True\n",
        encoding="utf-8",
    )

    router_file = tmp_path / "router.py"
    router_file.write_text(
        "from auth import AuthService\n\ndef login_endpoint():\n    svc = AuthService()\n    return svc.login('alice')\n",
        encoding="utf-8",
    )

    indexer = SymbolIndexer(root_path=tmp_path, revision="rev_cross")
    indexer.index_all()

    # Find by name
    auth_syms = indexer.find_by_name("AuthService")
    assert len(auth_syms) == 1
    auth_sym = auth_syms[0]
    assert auth_sym.file_path == "auth.py"

    # Cross reference resolution
    login_syms = indexer.find_by_name("login")
    assert len(login_syms) == 1
    login_sym = login_syms[0]
    assert login_sym.container_name == "AuthService"


def test_smart_retrieval_and_ranking(tmp_path: Path):
    # Setup test workspace
    auth_dir = tmp_path / "security"
    auth_dir.mkdir()
    (auth_dir / "authenticator.py").write_text(
        "class UserAuthenticator:\n    def verify_token(self, token: str) -> bool:\n        return True\n",
        encoding="utf-8",
    )

    calc_dir = tmp_path / "math"
    calc_dir.mkdir()
    (calc_dir / "calculator.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n",
        encoding="utf-8",
    )

    indexer = SymbolIndexer(root_path=tmp_path, revision="rev_sr")
    indexer.index_all()

    engine = SmartRetrievalEngine(indexer=indexer)
    res = engine.search("Where is user authentication token verified?")

    assert res.total_matches >= 1
    top = res.matches[0]
    assert "authenticator.py" in top.file_id
    assert top.relevance_tier in ("HIGH", "MEDIUM")
    assert any("verify_token" in reason or "UserAuthenticator" in reason or "auth" in reason for reason in top.match_reasons)
