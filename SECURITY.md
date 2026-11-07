# Security Policy

## Threat Model & Security Boundaries

RepoDNA is designed to inspect untrusted source repositories safely. The platform enforces strict security guardrails across the CLI, core engine, and FastAPI server:

1. **Zero Code Execution**:
   - RepoDNA performs **100% static analysis** using Tree-sitter CST/AST parsers and static scanners.
   - Repository code, build scripts, `setup.py`, `package.json` lifecycle scripts, and Git hooks are **never executed**.
2. **Git Clone Hardening & Honest Isolation Boundaries**:
   - Remote repositories are cloned into isolated temporary directories (`tempfile.mkdtemp`) with:
     - **Environment Allowlisting (`build_hardened_git_env`)**: Only minimal OS/runtime environment variables (`PATH`, `SYSTEMROOT`, `TEMP`, `SSL_CERT_*`, `LANG`) are passed to `git`; ambient credentials/tokens (`GITHUB_TOKEN`, `AWS_*`, `SSH_AUTH_SOCK`) are stripped.
     - **User / Global / System Config Isolation**: `GIT_CONFIG_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL=<empty_file>`, `HOME=<temp_dir>`, and `XDG_CONFIG_HOME=<temp_dir>` prevent host `~/.gitconfig` or `/etc/gitconfig` (`url.insteadOf`, credential helpers, custom transports) from influencing the clone.
     - **Hook, Symlink & Submodule Disabling**: `-c core.hooksPath=<empty_dir>`, `-c core.symlinks=false`, `-c core.quotepath=false`, and `-c submodule.recurse=false`.
     - **Protocol & Redirect Restrictions**: `-c protocol.allow=never`, `-c protocol.https.allow=always`, `-c protocol.file.allow=never`, and `-c http.followRedirects=false` (blocks open-redirect SSRF pivots from GitHub to internal hosts).
     - **Process Tree Timeout & Cleanup**: Clones run in a dedicated OS process group (`CREATE_NEW_PROCESS_GROUP` on Windows, `start_new_session=True` on POSIX) with `stdin=subprocess.DEVNULL`, `-c http.lowSpeedLimit=1024`, `-c http.lowSpeedTime=15`, and full child process tree termination (`taskkill /F /T` or `os.killpg`) on timeout or cancellation.
     - **What Is Not Guaranteed**: RepoDNA does **not** create an OS-level container/VM or filesystem quota mount during `git clone`. Packfile size during network transfer is bounded by `--depth 50 --single-branch --no-tags`, `-c pack.windowMemory=32m`, and the wall-clock `timeout_seconds`, while post-clone scanning enforces strict `max_files`, `max_file_size_bytes`, and `max_total_size_bytes` caps before reading file contents. Temporary clone directories are unconditionally wiped upon completion, timeout, or cancellation.
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
