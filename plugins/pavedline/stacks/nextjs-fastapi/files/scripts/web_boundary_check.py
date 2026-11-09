#!/usr/bin/env python3
# ruff: noqa: E501  (wide lists and comments in this one script)
"""Next.js is frontend only: the web app and the website hold no backend.

Fails (exit 1) when apps/web or apps/site contains
  * a route handler (route.<ts|tsx|js|jsx|mjs|cjs> under any app/ or src/app/ folder) other than /healthz and the
    auth-cookie proxy under app/auth/, or anything under pages/api/,
  * a server action (a "use server" directive anywhere in a file),
  * an import, dynamic import or require of a database or ORM package (middleware.ts and proxy.ts included), or such a
    package in package.json.
The API (services/api) is the only backend; a form or a mutation calls it. Exit 2 on a usage error.

Run from the repository root:  python3 scripts/web_boundary_check.py [--root .]
"""

import argparse
import json
import pathlib
import re
import sys

APPS = ("web", "site")
# Build output and dependencies, ONLY as top-level folders of an app (never an arbitrary path part: `app/dist/route.ts`
# is still a route).
SKIP_TOP_DIRS = {"node_modules", ".next", "out"}
SOURCE_SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts", ".mdx"}
ROUTE_RE = re.compile(r"^route\.(ts|tsx|js|jsx|mjs|cjs|mts|cts)$")
# Route folders (relative to the nearest `app/`) that may hold a route handler, each with its reason.
ALLOWED_ROUTE_DIRS = {
    "healthz": "the pod's own liveness/readiness probe; it answers without calling the API or a database",
    "auth": "the one place a session cookie is set: a thin proxy to the API's authentication, never business logic",
}
# A server action is any "use server" directive, wherever it stands (statement or function body, with or without `;`).
# Deliberately broad: a false positive is fixed by rewording, a false negative ships a backend.
USE_SERVER_RE = re.compile(r"""["'`]use server["'`]""")
DB_PACKAGES = (
    "@prisma/client",
    "prisma",
    "drizzle-orm",
    "drizzle-kit",
    "pg",
    "pg-pool",
    "pg-promise",
    "pg-native",
    "postgres",
    "postgres.js",
    "slonik",
    "mysql",
    "mysql2",
    "mariadb",
    "mongodb",
    "mongoose",
    "typeorm",
    "sequelize",
    "knex",
    "kysely",
    "better-sqlite3",
    "sqlite3",
    "@libsql/client",
    "@neondatabase/serverless",
    "@vercel/postgres",
    "@supabase/supabase-js",
    "@planetscale/database",
    "redis",
    "ioredis",
    "@upstash/redis",
    "mikro-orm",
    "@mikro-orm/core",
    "objection",
)
BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)
# import "x" | import x from "x" | export * from "x" | import("x") | import(`x`) | require("x"), quotes ' " or `.
IMPORT_RE = re.compile(r"""(?:\bfrom|\bimport|\brequire)\s*\(?\s*(["'`])([^"'`\n]+)\1""")


def is_db_module(name: str) -> bool:
    return any(name == pkg or name.startswith(pkg + "/") for pkg in DB_PACKAGES)


def route_problem(parts: tuple[str, ...]) -> str | None:
    """parts: the path below the app folder, file name last. A route handler (any `route.<ext>` below an `app/` folder at
    any depth, so also src/app) outside the allow-list, or anything under pages/api, is a backend."""
    for i in range(len(parts) - 2):
        if parts[i] == "pages" and parts[i + 1] == "api":
            return "pages/api handler (the API is the only backend)"
    if ROUTE_RE.match(parts[-1]) and "app" in parts[:-1]:
        sub = parts[parts.index("app") + 1 : -1]
        if not (sub and sub[0] in ALLOWED_ROUTE_DIRS):
            allowed = " and ".join("/" + d for d in ALLOWED_ROUTE_DIRS)
            return f"route handler (the API is the only backend; allowed: {allowed})"
    return None


def check_app(root: pathlib.Path, app: str) -> list[str]:
    base = root / "apps" / app
    problems: list[str] = []
    if not base.is_dir():
        return problems
    for path in sorted(base.rglob("*")):
        rel_parts = path.relative_to(base).parts
        if rel_parts[0] in SKIP_TOP_DIRS or not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if path.suffix in SOURCE_SUFFIXES or "pages" in rel_parts:
            msg = route_problem(rel_parts)
            if msg:
                problems.append(f"{rel}: {msg}")
        if path.suffix in SOURCE_SUFFIXES:
            text = path.read_text(errors="replace")
            if USE_SERVER_RE.search(text):
                problems.append(f'{rel}: server action ("use server")')
            for match in IMPORT_RE.finditer(BLOCK_COMMENT_RE.sub(" ", text)):
                if is_db_module(match.group(2)):
                    problems.append(f"{rel}: imports the database package {match.group(2)}")
        if path.name == "package.json":
            try:
                data = json.loads(path.read_text())
            except json.JSONDecodeError:
                problems.append(f"{rel}: not valid JSON")
                continue
            for key in ("dependencies", "devDependencies", "optionalDependencies"):
                for dep in data.get(key, {}):
                    if is_db_module(dep):
                        problems.append(f"{rel}: depends on the database package {dep}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path("."), help="repository root")
    args = parser.parse_args()
    root = args.root.resolve()
    if not (root / "apps").is_dir():
        print(f"usage error: {root / 'apps'} does not exist", file=sys.stderr)
        return 2
    problems = [p for app in APPS for p in check_app(root, app)]
    for p in problems:
        print(p)
    if problems:
        print(f"web boundary check: {len(problems)} problem(s). Next.js is frontend only.", file=sys.stderr)
        return 1
    print("web boundary check: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
