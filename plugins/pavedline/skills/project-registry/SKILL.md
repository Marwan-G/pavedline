---
name: project-registry
description: Keeps RUN.md, SERVICES.md and LINKS.md current in a Pavedline product repository. Records what each service is, where its dashboard and keys live, the owner and the rotation, and never a secret value. Use whenever a service, command or link is added or changes.
---

# project-registry

Three files at the repository root are the project's registry. Update them in the same change that makes them out of date.

## SERVICES.md

One row per external service, in the table already in the file: service · what it does · dashboard · where its secrets live · owner · rotation.

- **Where its secrets live** names the place: for example "secret manager, path `app/payments`", or "GitHub Actions secret `NAME`", or "`.env.local` on the developer's machine, not committed". Write the place, never the value. Never a key, token, password or connection string, not even a partial or masked one. This is never the value; if you are unsure whether a string is a secret, leave it out.
- **Owner** is a person or role who can rotate it. **Rotation** says how often and how.
- Add the row before the service is adopted, and only after the founder approved it (state what it is, what it does, why nothing already in use does it, and its verified cost). Any step that needs a dashboard click or an account the user must create also goes in `WAITING.md`.
- Remove a row when the service is removed, and note the removal in the commit message.

## RUN.md

The commands to install, test, start the local cluster and run the app. Keep each command copy-pasteable. Run a command before writing it down; if you could not run it, mark it "(unverified)". Update it whenever a slice changes how to build, test or run.

## LINKS.md

One line each, with a word on what it is for: design files, repositories, dashboards, the status page, the issue tracker. A link to a private dashboard is fine; a link that embeds a token is not.

## Checks before committing

1. Search the three files for anything that looks like a secret (long random strings, `sk_`, `ghp_`, `Bearer`, private-key headers). Remove it and tell the user.
2. Every service in the code and configuration has a row.
3. Every `Fn` in `WAITING.md` that names a service matches a row.
