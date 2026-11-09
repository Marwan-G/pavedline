#!/usr/bin/env python3
# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false
# (the contract is untyped YAML; the walkers below read it defensively)
"""Compare the FastAPI app with the OpenAPI contract (docs/api/openapi.yaml).

For every operation (method + path, path parameters normalised) and every 2xx JSON response, compares
the response's field names and JSON types (integer, number, string,
nullable). An operation the app serves that the contract does not describe fails.
A contract operation the app does not serve yet is listed as "not built yet"; it fails only with
--feature-complete. Health and docs routes are not in the OpenAPI document and are not compared.

Run (from the repository root):
  uv run --project services/api python scripts/contract_check.py \\
      --app app.main:app --contract docs/api/openapi.yaml [--feature-complete]

--app is `module:attribute`; the attribute is a FastAPI app or a function returning one. --app-dir
(default: services/api next to this script's folder) is put on sys.path so `app.main` is importable
from any working directory.

Exit codes: 0 ok, 1 differences, 2 usage error.
"""

import argparse
import importlib
import os
import pathlib
import re
import sys
from typing import Any

HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
Doc = dict[str, Any]


def normalise(path: str) -> str:
    return re.sub(r"\{[^}]*\}", "{}", path)


def resolve(schema: Any, doc: Doc, seen: tuple[str, ...] = ()) -> Any:
    while isinstance(schema, dict) and "$ref" in schema:
        ref = str(schema["$ref"])
        if ref in seen or not ref.startswith("#/"):
            return {}
        node: Any = doc
        for part in ref[2:].split("/"):
            node = node.get(part.replace("~1", "/").replace("~0", "~"), {}) if isinstance(node, dict) else {}
        seen = (*seen, ref)
        schema = node
    return schema


def type_set(schema: Any, doc: Doc, seen: tuple[str, ...] = ()) -> frozenset[str]:
    """The JSON types a schema allows ("null" included); empty means the schema does not say."""
    ref = schema.get("$ref") if isinstance(schema, dict) else None
    if ref is not None:
        if ref in seen:
            return frozenset()
        seen = (*seen, str(ref))
    schema = resolve(schema, doc)
    if not isinstance(schema, dict):
        return frozenset()
    types: set[str] = set()
    declared = schema.get("type")
    if isinstance(declared, str):
        types.add(declared)
    elif isinstance(declared, list):
        types.update(str(x) for x in declared)
    for key in ("allOf", "anyOf", "oneOf"):
        for member in schema.get(key, []):
            types |= type_set(member, doc, seen)
    if not types and "properties" in schema:
        types.add("object")
    if not types and "items" in schema:
        types.add("array")
    return frozenset(types)


def field_names(
    schema: Any, doc: Doc, prefix: str = "", seen: tuple[str, ...] = ()
) -> dict[str, frozenset[str]]:
    """Dotted name -> JSON types of every property below `schema`; arrays add `[]`. Unions merge."""
    names: dict[str, frozenset[str]] = {}
    ref = schema.get("$ref") if isinstance(schema, dict) else None
    if ref is not None:
        if ref in seen:
            return names
        seen = (*seen, str(ref))
    schema = resolve(schema, doc)
    if not isinstance(schema, dict):
        return names
    for key in ("allOf", "anyOf", "oneOf"):
        for member in schema.get(key, []):
            names.update(field_names(member, doc, prefix, seen))
    for name, sub in (schema.get("properties") or {}).items():
        path = f"{prefix}.{name}" if prefix else name
        names[path] = type_set(sub, doc)
        names.update(field_names(sub, doc, path, seen))
    if "items" in schema:
        names.update(field_names(schema["items"], doc, prefix + "[]", seen))
    return names


def operations(doc: Doc) -> dict[tuple[str, str], Any]:
    ops: dict[tuple[str, str], Any] = {}
    for path, item in (doc.get("paths") or {}).items():
        for method, op in (item or {}).items():
            if method.lower() in HTTP_METHODS:
                ops[(method.upper(), normalise(path))] = (path, op)
    return ops


def success_fields(op: Any, doc: Doc) -> dict[str, dict[str, frozenset[str]]]:
    out: dict[str, dict[str, frozenset[str]]] = {}
    for status, response in ((op or {}).get("responses") or {}).items():
        if not str(status).startswith("2"):
            continue
        resolved = resolve(response, doc)
        media = ((resolved or {}).get("content") or {}).get("application/json")
        out[str(status)] = field_names((media or {}).get("schema", {}), doc) if media else {}
    return out


DEFAULT_APP_DIR = pathlib.Path(__file__).resolve().parent.parent / "services/api"


def load_app(spec: str, app_dir: pathlib.Path) -> Any:
    module_name, _, attr = spec.partition(":")
    if not module_name or not attr:
        raise ValueError("--app must look like module:attribute")
    sys.path.insert(0, str(app_dir))
    os.environ.setdefault("APP_ENV", "test")
    os.environ.setdefault("DATABASE_URL", "postgresql://app_runtime:unused@127.0.0.1:1/unused")
    module = importlib.import_module(module_name)
    obj = getattr(module, attr)
    return obj() if callable(obj) and not hasattr(obj, "openapi") else obj


def compare(app_doc: Doc, contract: Doc, feature_complete: bool) -> tuple[list[str], list[str]]:
    problems: list[str] = []
    notes: list[str] = []
    served = operations(app_doc)
    promised = operations(contract)
    for key, (path, op) in sorted(served.items()):
        label = f"{key[0]} {path}"
        if key not in promised:
            problems.append(f"{label}: served by the app but not in the contract")
            continue
        app_fields = success_fields(op, app_doc)
        contract_fields = success_fields(promised[key][1], contract)
        for status, names in sorted(app_fields.items()):
            if status not in contract_fields:
                problems.append(f"{label}: the app answers {status} but the contract does not")
                continue
            promised_names = contract_fields[status]
            only_app = sorted(set(names) - set(promised_names))
            only_contract = sorted(set(promised_names) - set(names))
            for field in sorted(set(names) & set(promised_names)):
                a, c = names[field], promised_names[field]
                if a and c and a != c:  # an unspecified type (empty) is not compared
                    problems.append(
                        f"{label} {status}: field {field} type differs; app {sorted(a)}, contract {sorted(c)}"
                    )
            if only_app or only_contract:
                problems.append(
                    f"{label} {status}: response fields differ; app only: {only_app or '-'}; "
                    f"contract only: {only_contract or '-'}"
                )
    for key, (path, _) in sorted(promised.items()):
        if key not in served:
            notes.append(f"not built yet: {key[0]} {path}")
    if feature_complete:
        problems += notes
    return problems, notes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare the FastAPI app with the OpenAPI contract.")
    parser.add_argument("--app", required=True, help="module:attribute (an app, or a function returning one)")
    parser.add_argument(
        "--app-dir",
        type=pathlib.Path,
        default=DEFAULT_APP_DIR,
        help="put on sys.path (default: %(default)s)",
    )
    parser.add_argument("--contract", required=True, type=pathlib.Path, help="path to docs/api/openapi.yaml")
    parser.add_argument(
        "--feature-complete",
        action="store_true",
        help="also fail on contract operations the app does not serve yet",
    )
    args = parser.parse_args(argv)
    import yaml  # noqa: PLC0415 - dev dependency, imported late so `--help` works without it

    try:
        contract = yaml.safe_load(args.contract.read_text())
        app_doc = load_app(args.app, args.app_dir).openapi()
    except (OSError, ValueError, ImportError, AttributeError, yaml.YAMLError) as exc:
        print(f"contract_check: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    if not isinstance(contract, dict):
        print("contract_check: the contract is not a YAML mapping", file=sys.stderr)
        return 2
    problems, notes = compare(app_doc, contract, args.feature_complete)
    for line in notes if not args.feature_complete else []:
        print(line)
    for line in problems:
        print(line)
    if problems:
        print(f"contract_check: {len(problems)} problem(s)")
        return 1
    print("contract_check: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
