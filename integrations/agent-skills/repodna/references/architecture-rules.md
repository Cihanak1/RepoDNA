# RepoDNA Architectural Rules & Metrics Reference

## 1. Robert C. Martin Coupling & Instability Metrics
- **Afferent Coupling ($C_a$ / Fan-In):** Number of internal repository modules that depend upon this module. High fan-in indicates responsibility and architectural centrality (hub module).
- **Efferent Coupling ($C_e$ / Fan-Out):** Number of internal repository modules that this module depends upon. High fan-out indicates high dependency complexity.
- **Instability Index ($I$):**
  $$I = \frac{C_e}{C_a + C_e}$$
  - $I = 0.0$: Maximally stable / rigid (heavy incoming dependencies, zero outgoing dependencies).
  - $I = 1.0$: Maximally unstable / flexible (zero incoming dependencies, only outgoing dependencies).

## 2. Architectural Rules Catalog
| Rule ID | Category | Title | Description | Severity |
| :--- | :--- | :--- | :--- | :--- |
| `ARCH-001` | Cycles | No Circular Dependencies | Modules must not participate in mutually recursive dependency cycles (Tarjan SCC). | Critical |
| `ARCH-002` | Coupling | Fan-Out Threshold | Individual modules should not exceed efferent coupling threshold ($C_e \le 12$). | Warning |
| `ARCH-003` | Coupling | Stable Dependencies Principle | Unstable modules ($I \to 1$) must depend on more stable abstractions ($I \to 0$). | Warning |
| `ARCH-004` | Complexity | Single File LOC Cap | Source files should remain maintainable ($LOC \le 1,000$). | Info |
| `ARCH-005` | Hygiene | Dead Code / Orphan Files | Non-root files without incoming or outgoing internal dependencies. | Info |
| `ARCH-006` | Hygiene | Layered Architecture Isolation | Core domain modules must not import user interface or transport layers. | Warning |
| `SEC-001` | Security | Secret & Sensitive File Leak | Repository must not contain committed private keys, JWT secrets, or unignored `.env` files. | Critical |

## 3. Honest AST Coverage Semantics
- **Full AST:** Parsed with language-specific Tree-sitter grammar (Python, TypeScript, JavaScript, Go, Rust). Full symbol and dependency resolution.
- **Partial Static:** Static pattern matching only (e.g. C# `using`, Ruby `require`). Internal graph not verified.
- **Unsupported:** File count and LOC tracked, but dependencies cannot be verified.
- **`N/A` Health Score Guarantee:** When AST coverage is insufficient, RepoDNA marks health as `N/A` rather than fabricating an artificial pass.
