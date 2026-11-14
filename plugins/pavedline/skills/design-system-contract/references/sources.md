# Sources (checked on the web 2026-11-08)

Facts at a date, not rules; re-check before relying on them.

| Fact | Value | URL | Date |
|---|---|---|---|
| Figma plugin install | `claude plugin install figma@claude-plugins-official`; connect and sign in afterwards (`/mcp`) | https://developers.figma.com/docs/figma-mcp-server/remote-server-installation | 2026-11-08 |
| Figma plugin skills | `figma-use`, `figma-generate-library`, `figma-generate-design`, `figma-use-figjam`, `figma-code-connect` exist as skills of the installed plugin (figma@claude-plugins-official 2.2.157, checked in the plugin's own skills directory) | the installed plugin | 2026-11-08 |
| Code Connect seat rule | the help centre says "Professional, Education, Organization, Government, and Enterprise plans" and "Requires a Full or Dev seat" | https://help.figma.com/hc/en-us/articles/23920389749655-Code-Connect | 2026-11-08 |
| Code Connect through MCP | in a real run the plugin's mapping tool refused a Professional plan with a Full seat: "Code connections can only be made in libraries that are in Organization or Enterprise plans." The help-centre rule above is not enough; try the mapping and fall back to the name table | the Figma MCP `add_code_connect_map` tool | 2026-11-08 |
| ui-ux-pro-max install | a Claude Code plugin: `/plugin marketplace add nextlevelbuilder/ui-ux-pro-max-skill` then `/plugin install ui-ux-pro-max@ui-ux-pro-max-skill` (marketplace `ui-ux-pro-max-skill`, plugin `ui-ux-pro-max`), MIT; optional (founder ruling 2026-11-09): not a plugin dependency, `doctor` lists it as optional, step 7 uses it only if installed | https://github.com/nextlevelbuilder/ui-ux-pro-max-skill | 2026-11-08 |
| impeccable install | `/plugin marketplace add pbakaus/impeccable` then install `impeccable@impeccable`; Apache-2.0; optional | https://github.com/pbakaus/impeccable | 2026-11-08 |
| Figma MCP limits | read tools only, on a Full or Dev seat: Professional "Up to 200 per day, 10 per minute", Organization 200 a day and 15 a minute, Enterprise 600 a day and 20 a minute; View and Collab seats 20 a month; "Tools that write to Figma files are exempt" | https://developers.figma.com/docs/figma-mcp-server/rate-limits-access/ | 2026-11-14 |
| Touch target sizes | WCAG 2.2 SC 2.5.8 (AA): "at least 24 by 24 CSS pixels"; SC 2.5.5 (enhanced): 44 by 44 CSS pixels | https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html | 2026-11-14 |

Vendor prices are never copied from here; check them for each approved service.
