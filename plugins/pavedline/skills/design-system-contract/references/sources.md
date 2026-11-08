# Sources (checked on the web 2026-11-08)

Facts at a date, not rules; re-check before relying on them.

| Fact | Value | URL | Date |
|---|---|---|---|
| Figma plugin install | `claude plugin install figma@claude-plugins-official`; connect and sign in afterwards (`/mcp`) | https://developers.figma.com/docs/figma-mcp-server/remote-server-installation | 2026-11-08 |
| Figma plugin skills | `figma-use`, `figma-generate-library`, `figma-generate-design`, `figma-use-figjam`, `figma-code-connect` exist as skills of the installed plugin (figma@claude-plugins-official 2.2.157, checked in the plugin's own skills directory) | the installed plugin | 2026-11-08 |
| Code Connect seat rule | the help centre says "Professional, Education, Organization, Government, and Enterprise plans" and "Requires a Full or Dev seat" | https://help.figma.com/hc/en-us/articles/23920389749655-Code-Connect | 2026-11-08 |
| Code Connect through MCP | in a real run the plugin's mapping tool refused a Professional plan with a Full seat: "Code connections can only be made in libraries that are in Organization or Enterprise plans." The help-centre rule above is not enough; try the mapping and fall back to the name table | the Figma MCP `add_code_connect_map` tool | 2026-11-08 |
| ui-ux-pro-max install | a Claude Code plugin: `/plugin marketplace add nextlevelbuilder/ui-ux-pro-max-skill` then `/plugin install ui-ux-pro-max@ui-ux-pro-max-skill` (marketplace `ui-ux-pro-max-skill`, plugin `ui-ux-pro-max`), MIT; so it is a plugin dependency | https://github.com/nextlevelbuilder/ui-ux-pro-max-skill | 2026-11-08 |
| impeccable install | `/plugin marketplace add pbakaus/impeccable` then install `impeccable@impeccable`; Apache-2.0; optional | https://github.com/pbakaus/impeccable | 2026-11-08 |

Vendor prices are never copied from here; check them for each approved service.
