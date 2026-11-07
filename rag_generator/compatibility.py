from rag_generator.models import Component, Selection, ValidationIssue

SECRET_MARKERS = ("api_key", "secret", "password", "token", "credential")


def validate_selection(
    selection: Selection,
    catalog: dict[str, Component],
    *,
    require_implemented: bool = True,
    require_complete: bool = True,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    selected: list[Component] = []

    if not selection.project_name.strip():
        issues.append(ValidationIssue("invalid_project_name", "Project name cannot be empty"))

    for component_id in selection.components:
        component = catalog.get(component_id)
        if component is None:
            issues.append(ValidationIssue("unknown_component", f"Unknown component: {component_id}"))
        else:
            selected.append(component)

    if len(set(selection.components)) != len(selection.components):
        issues.append(ValidationIssue("duplicate_component", "A component may be selected only once"))

    if require_implemented:
        for component in selected:
            if component.status != "implemented":
                issues.append(ValidationIssue(
                    "not_implemented", f"{component.id} is visible in the roadmap but has no renderer yet"
                ))

    providers = {capability for item in selected for capability in item.provides}
    ids = {item.id for item in selected}
    for item in selected:
        for requirement in item.requires:
            if requirement not in providers:
                issues.append(ValidationIssue(
                    "missing_capability", f"{item.id} requires capability '{requirement}'"
                ))
        for conflict in item.conflicts:
            if conflict in ids:
                issues.append(ValidationIssue("conflict", f"{item.id} conflicts with {conflict}"))

    categories: dict[str, list[str]] = {}
    for item in selected:
        categories.setdefault(item.category, []).append(item.id)
    for category, component_ids in categories.items():
        if category in {"chunker", "embedding", "vector_store", "retrieval"} and len(component_ids) > 1:
            issues.append(ValidationIssue(
                "category_cardinality",
                f"Choose one {category}; selected: {', '.join(component_ids)}",
            ))

    if require_complete:
        for category in ("parser", "chunker", "embedding", "vector_store", "retrieval"):
            if category not in categories:
                issues.append(ValidationIssue(
                    "missing_category", f"A complete repository requires one {category} component"
                ))

    dimension = selection.settings.get("embedding_dimensions")
    embeddings = [item for item in selected if item.category == "embedding"]
    stores = [item for item in selected if item.category == "vector_store"]
    if dimension is not None:
        if not isinstance(dimension, int) or dimension <= 0:
            issues.append(ValidationIssue("invalid_dimension", "embedding_dimensions must be positive"))
        for item in embeddings + stores:
            if item.embedding_dimensions and dimension not in item.embedding_dimensions:
                issues.append(ValidationIssue(
                    "dimension_mismatch",
                    f"{item.id} does not support embedding dimension {dimension}",
                ))

    requested_runtime = selection.settings.get("runtime", "sync")
    if requested_runtime not in {"sync", "async"}:
        issues.append(ValidationIssue("invalid_runtime", "runtime must be 'sync' or 'async'"))
    for item in selected:
        if item.runtime != "either" and item.runtime != requested_runtime:
            issues.append(ValidationIssue(
                "runtime_mismatch", f"{item.id} requires {item.runtime} runtime"
            ))

    for key, value in selection.settings.items():
        if any(marker in key.lower() for marker in SECRET_MARKERS) and value:
            issues.append(ValidationIssue(
                "secret_value", f"Do not put secret values in settings ({key}); use an environment variable"
            ))

    chunk_size = selection.settings.get("chunk_size_words", 350)
    chunk_overlap = selection.settings.get("chunk_overlap_words", 60)
    if not isinstance(chunk_size, int) or chunk_size <= 0:
        issues.append(ValidationIssue("invalid_chunking", "chunk_size_words must be positive"))
    elif not isinstance(chunk_overlap, int) or not 0 <= chunk_overlap < chunk_size:
        issues.append(ValidationIssue(
            "invalid_chunking", "chunk_overlap_words must be non-negative and smaller than chunk_size_words"
        ))

    return _deduplicate(issues)


def _deduplicate(issues: list[ValidationIssue]) -> list[ValidationIssue]:
    return list(dict.fromkeys(issues))
