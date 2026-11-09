#!/usr/bin/env bash
# Push a branch (or a commit, given by its sha) of the product repo (the current directory) to the local git server as branch main of
# git://kind-git:9418/<project>.git, which Argo CD in the cluster syncs from. Push is host-only: the server's daemon is
# read-only, so the transport is `docker exec` into the kind-git container (git's ext:: transport, enabled for this
# one command only). Force-pushes: the local server is a mirror of the branch being deployed.
set -euo pipefail

usage() { echo "usage: push.sh <project> [<branch>|<commit-sha>]  (run inside the product repo)" >&2; exit 2; }
if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then usage; fi
PROJECT="$1"
if ! [[ "$PROJECT" =~ ^[a-z0-9]([-a-z0-9]{0,40}[a-z0-9])?$ ]]; then
  echo "error: project must be a lowercase DNS label (a-z, 0-9, -), got: $PROJECT" >&2
  exit 2
fi
REF="${2:-$(git rev-parse --abbrev-ref HEAD)}"
if git show-ref --verify --quiet "refs/heads/${REF}"; then
  SRC="refs/heads/${REF}"
elif [[ "$REF" =~ ^[0-9a-f]{7,40}$ ]] && SRC="$(git rev-parse --verify --quiet "${REF}^{commit}")"; then
  : # a commit that is on no branch (the deploy script's deploy commit): pushed by its full sha
else
  echo "error: not a branch or a commit of this repository: $REF" >&2
  exit 2
fi
if [ "$(docker inspect -f '{{.State.Running}}' kind-git 2>/dev/null || true)" != 'true' ]; then
  echo "error: the kind-git container is not running; run up.sh ${PROJECT}" >&2
  exit 1
fi
git -c protocol.ext.allow=always push --force "ext::docker exec -i kind-git %S /srv/git/${PROJECT}.git" "${SRC}:refs/heads/main"
