# Local git server for the kind test bed: Argo CD in the cluster syncs from git://kind-git:9418/<project>.git.
# A local tool, never deployed. The daemon is READ-ONLY (upload-pack only): anything on the kind docker network can
# read, nothing can push. A push to the repo Argo CD auto-syncs add-ons from would be a cluster takeover, so pushes
# happen only from this machine, through `docker exec` (push.sh), and the daemon publishes no host port.
# up.sh passes the pinned base image (versions.env GIT_SERVER_BASE_IMAGE) as BASE; it is recorded as a label so up.sh
# can tell when the running container was built from an older pin.
ARG BASE
FROM ${BASE}
ARG BASE
LABEL org.opencontainers.image.base.digest="${BASE}"
RUN apk add --no-cache git git-daemon \
 && mkdir -p /srv/git \
 && git config --system --add safe.directory '*'
EXPOSE 9418
ENTRYPOINT ["git", "daemon", "--export-all", "--base-path=/srv/git", "--reuseaddr", "--informative-errors", "--verbose"]
CMD ["/srv/git"]
