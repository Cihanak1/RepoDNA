# Security Policy

## Threat Model & Security Boundaries

RepoDNA is designed to inspect untrusted source repositories safely. The platform enforces strict security guardrails across the CLI, core engine, and FastAPI server:

1. **Zero Code Execution**:
   - RepoDNA performs **100% static analysis** using Tree-sitter CST/AST parsers and static scanners.
   - Repository code, build scripts, `setup.py`, `package.json` lifecycle scripts, and Git hooks are **never executed**.
2. **Git Clone Hardening**:
   - Remote repositories are cloned into isolated temporary directories (`tempfile.mkdtemp`) with:
     - `-c core.hooksPath=<empty_dir>` (prevents malicious Git hook execution)
     - `-c core.symlinks=false` and `-c core.quotepath=false` (prevents symlink checkout attacks and preserves Unicode paths)
     - `-c protocol.file.allow=never` and `-c submodule.recurse=false`
     - `-c http.lowSpeedLimit=1024` and `-c http.lowSpeedTime=15` (mitigates slowloris tarpit attacks)
     - `GIT_TERMINAL_PROMPT=0`, `GIT_CONFIG_NOSYSTEM=1`, `GIT_LFS_SKIP_SMUDGE=1`, and `stdin=subprocess.DEVNULL`
   - Temporary clone directories are unconditionally wiped upon scan completion, timeout, or cancellation.
3. **SSRF & Git URL Validation**:
   - Only canonical `https://github.com/<owner>/<repo>` URLs are accepted.
   - `http://`, `ssh://`, `git://`, `file://`, custom ports, query strings, fragments, embedded credentials (`user:token@`), `localhost`, and IPv4/IPv6 literals (`127.0.0.1`, `169.254.169.254`, `[::1]`) are rejected before any network call is made.
   - Branch/tag names are validated against a strict allowlist regex to block Git option injection (`--upload-pack`, leading `-`, `..`).
4. **Symlink & Path Traversal Protection**:
   - Local scans require explicit user initiation; RepoDNA never performs background or automatic disk scanning.
   - Symbolic links and NTFS junctions are skipped (`follow_symlinks=False`), and every candidate path is verified via `Path.resolve().is_relative_to(root_resolved)`.
   - System and credential directories (`/etc`, `/proc`, `C:\Windows`, `.ssh`, `.aws`, `.gnupg`) are explicitly blocked.
5. **Resource Exhaustion & DoS Limits**:
   - Configurable caps on `max_files` (default `2,500`), `max_file_size_bytes` (default `1 MB`), `max_total_size_bytes` (default `100 MB`), and `timeout_seconds` (default `60s`), plus instant job cancellation.
6. **Credential & Secret Redaction**:
   - Embedded URL credentials are stripped from error messages and logs.
   - Sensitive files (`.env`, `id_rsa`, `.pypirc`) are flagged by `SEC-001` without parsing or exposing their raw contents.

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in RepoDNA, please do **not** open a public issue with exploit details. Instead, report it privately via GitHub Security Advisories on the repository so a fix can be coordinated and released promptly.
