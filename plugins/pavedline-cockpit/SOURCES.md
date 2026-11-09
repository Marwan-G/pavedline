# Sources

Facts about Claude Code mods used by this plugin, checked 2026-11-09.

- Mod reference: https://code.claude.com/docs/en/plugins/mods/reference.md (2026-11-09). `hooks/hooks.json` `"modules"`, `register(on, options)`, the `ui.render` hook on the `Pane` render site, `turn.complete`, `$.fs`, `$.command.register` and the `command.run` hook.
- Mods overview: https://code.claude.com/docs/en/plugins/mods/overview.md (2026-11-09). Terminal needs Claude Code v2.1.287 or later (Desktop v2.1.286); in `claude -p` mods run but draw nothing.
- Types for the installed build (written by `plugin-authoring`, Claude Code 2.1.319, 2026-11-09): `$.fs.read` is relative to the session's working directory; reads over 4 MiB reject.
- A plugin skill is invoked as `/<plugin>:<skill>`, so `skills/status` is `/pavedline-cockpit:status`; the mod's own `pavedline-status` command is registered unprefixed.
