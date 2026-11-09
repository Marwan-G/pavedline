#!/usr/bin/env python3
"""Fail closed unless a plan only creates, updates, reads or leaves things alone.

Usage:  tofu show -json plan.out | python3 plan_check.py
        python3 plan_check.py plan.json

Rule: an applied plan shows 0 to destroy and nothing replaced. The check is an ALLOW-LIST of exact actions
(case-sensitive): ["no-op"], ["read"], ["create"], ["update"]. Everything else is listed and fails: delete, replace in
either order, "forget" (state surgery), unknown or mis-cased actions, an actions value that is not a list.

One deliberate exception: a lone ["delete"] of a `kubernetes_node_taint` is allowed and always printed. Those resources
are keyed by node, so a node removed or replaced by OKE removes its taint object; the node is gone, nothing is lost.
A replace of a taint (delete plus create) is not allowed.

`deferred_changes` (changes OpenTofu could not plan yet) get the same check, and their presence fails the run because
the plan is incomplete. `resource_drift` is not read: it reports differences already in the real world, not planned
actions, so it cannot make an apply destroy anything.

Exit 0 = clean, 1 = something would be destroyed, replaced or is unverifiable, 2 = the input is not a plan.
"""
import json
import sys

ALLOWED = ({"no-op"}, {"read"}, {"create"}, {"update"})
ALLOWED_LISTS = [sorted(a) for a in ALLOWED]
TAINT_TYPE = "kubernetes_node_taint"


class NotAPlan(Exception):
    pass


def _entries(plan: dict, key: str, required: bool) -> list:
    if key not in plan:
        if required:
            raise NotAPlan(f"no {key!r} list (is this `tofu show -json` of a plan file?)")
        return []
    items = plan[key]
    if not isinstance(items, list):
        raise NotAPlan(f"{key!r} is not a list")
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("change"), dict):
            raise NotAPlan(f"an entry of {key!r} is malformed")
    return items


def classify(item: dict) -> str:
    """Return 'ok', 'taint' (allowed delete) or 'bad'."""
    actions = item["change"].get("actions")
    if not isinstance(actions, list) or not all(isinstance(a, str) for a in actions):
        return "bad"
    if actions in ALLOWED_LISTS:
        return "ok"
    if actions == ["delete"] and item.get("type") == TAINT_TYPE:
        return "taint"
    return "bad"


def check(plan: dict) -> tuple[list, list, list]:
    if plan.get("format_version") is None:
        raise NotAPlan("no 'format_version'")
    changes = _entries(plan, "resource_changes", required=True)
    deferred = _entries(plan, "deferred_changes", required=False)
    if plan.get("errored") is True:
        raise NotAPlan("the plan is marked errored")
    bad, taints = [], []
    for item in changes + deferred:
        kind = classify(item)
        label = (item.get("address") or "<unknown>", item["change"].get("actions"))
        if kind == "bad":
            bad.append(label)
        elif kind == "taint":
            taints.append(label)
    return bad, taints, deferred


def main(argv: list[str]) -> int:
    try:
        raw = open(argv[1], encoding="utf-8").read() if len(argv) > 1 else sys.stdin.read()
        plan = json.loads(raw)
        if not isinstance(plan, dict):
            raise NotAPlan("not a JSON object")
        bad, taints, deferred = check(plan)
    except (OSError, ValueError, NotAPlan) as exc:
        print(f"plan_check: not a plan: {exc}", file=sys.stderr)
        return 2
    for address, _ in taints:
        print(f"allowed: taint of a removed node {address}")
    if deferred:
        print(f"{len(deferred)} deferred change(s): the plan is incomplete; do not apply")
    if bad or deferred:
        print(f"{len(bad)} resource(s) would be destroyed, replaced or are not plain create/update/read; do not apply:")
        for address, actions in bad:
            print(f"  {address}  ({actions!r})")
        return 1
    print("0 to destroy, 0 replaced")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
