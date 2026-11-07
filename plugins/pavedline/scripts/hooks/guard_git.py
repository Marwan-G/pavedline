#!/usr/bin/env python3
"""PreToolUse guard: no hook-skipping, no force-push to main/master."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

PROTECTED = {"main", "master"}
GLOBAL_VALUE_OPTS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path",
                     "--super-prefix", "--config-env"}
NAME_ARG_HINT = "name the branch explicitly (git push --force-with-lease origin <branch>)"


def _is_no_verify(t):
    # git accepts unambiguous long-option abbreviations (--no-ver, --no-verif).
    return t.startswith("--no-v") and "--no-verify".startswith(t)


def _is_force_flag(t):
    name = t.split("=", 1)[0]
    if t.startswith("--"):
        return name.startswith("--force") or (len(name) >= 4 and "--force".startswith(name))
    if t.startswith("-") and len(t) > 1:
        for ch in t[1:]:
            if ch == "f":
                return True
            if ch == "o":  # -o <push-option>: rest is a value
                return False
    return False


def _commit_short_n(t):
    if not t.startswith("-") or t.startswith("--") or len(t) < 2:
        return False
    for ch in t[1:]:
        if ch == "n":
            return True
        if ch in "mFCctSu":  # value-taking: remainder (or next token) is a value
            return False
    return False


def _dest(refspec):
    r = refspec.lstrip("+")
    d = r.rsplit(":", 1)[1] if ":" in r else r
    if d.startswith("refs/heads/"):
        d = d[len("refs/heads/"):]
    return d


def check_push(rest):
    forced, pos, delete = False, [], False
    for t in rest:
        if t.startswith("-"):
            if _is_force_flag(t):
                forced = True
            if t in ("--all", "--mirror"):
                pos.append(t)
            if t in ("--delete", "-d"):
                delete = True
        else:
            pos.append(t)
    flag_set = [p for p in pos if p in ("--all", "--mirror")]
    refs = [p for p in pos if p not in ("--all", "--mirror")][1:]  # first is the remote
    if forced and flag_set:
        return "Blocked: a forced push with --all/--mirror can overwrite main. Push one named branch instead."
    if forced and not refs:
        return ("Blocked: a forced push with no refspec pushes the current branch, which may be main. "
                + NAME_ARG_HINT)
    for r in refs:
        d = _dest(r)
        plus = r.startswith("+")
        deletion = delete or r.startswith(":")
        if d in PROTECTED and (forced or plus or deletion):
            return (f"Blocked: force-pushing to or deleting {d} is not allowed. "
                    "Open a pull request, or push a feature branch.")
        if (forced or plus) and (d in ("HEAD", "@") or "*" in d):
            return ("Blocked: this forced push may overwrite main (the destination is not a plain branch name). "
                    + NAME_ARG_HINT)
    return None


def check(command):
    for cmd in _common.shell_commands(command):
        _, verb, args = _common.unwrap(cmd)
        if verb != "git":
            continue
        i, sub = 0, None
        while i < len(args):
            t = args[i]
            if t in ("-c", "--config-env") and i + 1 < len(args):
                if "hookspath" in args[i + 1].lower():
                    return "Blocked: overriding core.hooksPath skips git hooks."
            if t.startswith("--config-env=") and "hookspath" in t.lower():
                return "Blocked: overriding core.hooksPath skips git hooks."
            if t in GLOBAL_VALUE_OPTS:
                i += 2
            elif t.startswith("-"):
                i += 1
            else:
                sub = t
                break
        rest = args[i + 1:] if sub else []
        if any(_is_no_verify(t) for t in args):
            return "Blocked: --no-verify skips git hooks. Fix what the hook reports instead."
        if sub == "commit" and any(_commit_short_n(t) for t in rest):
            return "Blocked: `git commit -n` is --no-verify and skips git hooks. Fix what the hook reports instead."
        if sub == "push":
            reason = check_push(rest)
            if reason:
                return reason
    return None


def main():
    event = _common.read_event()
    if event is None:
        sys.stderr.write("pavedline guard_git: empty or invalid hook input; allowing.\n")
        _common.allow()
    ti = event.get("tool_input")
    cmd = ti.get("command") if isinstance(ti, dict) else None
    if event.get("tool_name") == "Bash" and isinstance(cmd, str):
        reason = check(cmd)
        if reason:
            _common.block(reason)
    _common.allow()


if __name__ == "__main__":
    main()
