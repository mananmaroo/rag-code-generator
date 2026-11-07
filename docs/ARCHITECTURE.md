# Product architecture

## Product in one paragraph

RAG Code Generator is a visual-catalogue-backed product that turns an explicit, typed
selection of RAG capabilities into reviewed code modules or a complete runnable project.
It teaches the trade-offs of each option, rejects incompatible combinations before code
generation, supports customer-owned providers and infrastructure through environment
configuration, and uses deterministic versioned templates for the security-sensitive core;
an LLM may later explain or adapt bounded areas, but never silently invent the architecture.

## Layers

1. **Catalogue** — versioned component manifests: inputs, outputs, runtime mode,
   dependencies, conflicts, cost/latency notes, configuration, and template ownership.
2. **Selection** — the user's desired components and typed settings; contains references,
   never credentials.
3. **Compatibility engine** — resolves capabilities and validates cross-component
   invariants before rendering.
4. **Generation plan** — a stable list of files, dependencies, migrations, environment
   variables, and instructions to render.
5. **Renderer** — deterministic reviewed templates with atomic output and a lock manifest.
6. **Delivery** — individual files/modules or a complete repository archive.

```text
visual configurator / CLI
          |
     typed selection
          v
 catalogue + compatibility rules --X--> actionable validation errors
          |
     generation plan
          v
 versioned templates -> module or runnable repository + lock manifest
```

## Manifest contract

Each component has a stable ID and version, one category, capabilities it provides and
requires, conflicts, runtime mode, optional embedding dimension, configuration fields,
trade-off guidance, and implementation status. `implemented` means a reviewed renderer is
available; `proposed` makes future choices visible without allowing misleading generation.

## Security boundaries

- Selections and generated source contain environment-variable names, never secret values.
- Uploaded documents and customer code are untrusted; future conversion/OCR and code
  inspection run in isolated workers with resource limits and no default network access.
- Tenant authorization must occur before retrieval, not after results are fetched.
- Generated permissions should be least-privilege and deployment adapters should emit
  secret-manager references rather than credentials.
- The generator records exact component/template versions for reproducibility and upgrades.

## Architecture validation

| Requirement | Architectural answer | MVP evidence |
|---|---|---|
| À-la-carte components | Stable component IDs and category slots | Catalogue + selection JSON |
| Safe composition | Pre-render capability and invariant checks | Compatibility engine tests |
| BYO providers/accounts | Settings reference environment names only | Secret-value rejection |
| Module or repository downloads | Generation plan is file-granular | Repository mode first; module next |
| Tests/docs/local setup/eval | Required output contract | Generated files and tests |
| Three RAG tiers | Explicit template/tier metadata | Basic tier now; hybrid/agentic proposed |
| Teach trade-offs | Guidance fields in every manifest | CLI catalogue output |
| Avoid unnecessary agents | Agentic components are opt-in and proposed | No agent in MVP |

The MVP is deliberately narrow but validates every foundational boundary. Adding providers
or deployment targets becomes catalogue/template work, not a redesign of the generator.
