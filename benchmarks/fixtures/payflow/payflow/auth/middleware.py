"""Authentication middleware for HTTP API requests."""
from typing import Callable, Optional
from payflow.auth.jwt_handler import TokenService

class AuthenticationMiddleware:
    """Intercepts incoming API requests to validate Bearer tokens."""
    def __init__(self, token_service: TokenService) -> None:
        self.token_service = token_service

    def authenticate_request(self, auth_header: Optional[str]) -> str:
        """Extracts Bearer token and returns authenticated principal ID."""
        if not auth_header or not auth_header.startswith("Bearer "):
            raise PermissionError("Missing or invalid authorization header")
        raw_token = auth_header.split(" ", 1)[1]
        claims = self.token_service.decode_access_token(raw_token)
        return claims["sub"]

    def require_permissions(self, user_role: str, required_scope: str) -> bool:
        """Enforces RBAC permission scopes for protected operations."""
        admin_scopes = {"billing:admin", "ledger:write", "payments:refund"}
        return user_role == "admin" or required_scope not in admin_scopes
