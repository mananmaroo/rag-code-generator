import argparse
import json
from pathlib import Path

from rag_generator.catalog import load_catalog
from rag_generator.compatibility import validate_selection
from rag_generator.generator import generate_repository
from rag_generator.models import Selection
from rag_generator.web import serve


def _load_selection(path: Path) -> Selection:
    return Selection.from_dict(json.loads(path.read_text(encoding="utf-8")))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="raggen")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("catalog", help="list catalogue components")
    validate = commands.add_parser("validate", help="validate a selection")
    validate.add_argument("selection", type=Path)
    generate = commands.add_parser("generate", help="generate a repository")
    generate.add_argument("selection", type=Path)
    generate.add_argument("--output", type=Path, required=True)
    web = commands.add_parser("serve", help="run the visual configurator")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8080)
    web.add_argument("--database", type=Path, default=Path("work/raggen.db"))
    args = parser.parse_args(argv)
    if args.command == "serve":
        serve(args.host, args.port, args.database)
        return 0
    catalog = load_catalog()

    if args.command == "catalog":
        for item in catalog.values():
            print(f"{item.id:28} {item.status:11} {item.name} — {item.tradeoffs}")
        return 0

    selection = _load_selection(args.selection)
    issues = validate_selection(selection, catalog)
    if issues:
        for issue in issues:
            print(f"ERROR [{issue.code}] {issue.message}")
        return 2
    print("Selection is compatible.")
    if args.command == "validate":
        return 0

    components = [catalog[item] for item in selection.components]
    paths = generate_repository(selection, components, args.output)
    print(f"Generated {len(paths)} files in {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
