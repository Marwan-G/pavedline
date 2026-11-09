# syntax=docker/dockerfile:1
# Build (context is the REPOSITORY ROOT, the app needs the workspace packages):
#   docker build -f apps/web/Dockerfile -t web:dev .
# Run:   docker run --read-only --tmpfs /tmp --tmpfs /app/apps/web/.next/cache -e API_INTERNAL_URL=... -p 3000:3000 web:dev
# The base image is pinned by digest (index digest: linux/arm64 and linux/amd64).

FROM node:26.12.1-alpine@sha256:40cd011b55415bc894e45b02fdd5a5dfde056921b7d23a64c74f80497af48797 AS build
# Node 25 and later do not ship corepack, so pnpm is installed at the exact version of package.json "packageManager".
RUN npm install --global pnpm@11.28.8
WORKDIR /repo
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY apps/web/package.json apps/web/
COPY packages/api-client/package.json packages/api-client/
COPY packages/glossary/package.json packages/glossary/
COPY packages/tokens/package.json packages/tokens/
RUN pnpm install --frozen-lockfile --filter @app/web...
COPY tsconfig.base.json ./
COPY packages/api-client packages/api-client
COPY packages/glossary packages/glossary
COPY packages/tokens packages/tokens
COPY apps/web apps/web
ENV NEXT_TELEMETRY_DISABLED=1
RUN pnpm --filter @app/web build

FROM node:26.12.1-alpine@sha256:40cd011b55415bc894e45b02fdd5a5dfde056921b7d23a64c74f80497af48797 AS runtime
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
RUN addgroup -S -g 10001 app && adduser -S -u 10001 -G app -H -s /sbin/nologin app
WORKDIR /app
COPY --from=build --chown=10001:10001 /repo/apps/web/.next/standalone ./
COPY --from=build --chown=10001:10001 /repo/apps/web/.next/static ./apps/web/.next/static
COPY --from=build --chown=10001:10001 /repo/apps/web/scripts/boot-check.mjs ./scripts/boot-check.mjs
# Next.js writes its cache under .next/cache; the root filesystem is read-only in the cluster, so the chart mounts an
# emptyDir there (extraEmptyDirs). Created here so the path exists and belongs to the app user.
RUN mkdir -p /app/apps/web/.next/cache && chown 10001:10001 /app/apps/web/.next/cache
USER 10001:10001
# The in-image boot check: start the server and answer /healthz, or the build fails.
RUN node scripts/boot-check.mjs apps/web/server.js noindex
EXPOSE 3000
CMD ["node", "apps/web/server.js"]
