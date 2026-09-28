# Architecture Decision Records

This directory holds the project's ADRs (Architecture Decision Records) in
[MADR 3.0](https://adr.github.io/madr/) style. ADRs capture **consequential
architectural decisions** — technology choices, license, packaging, security
tradeoffs, deprecations. Bug fixes and tactical refactors do not belong here.

See [`_template.md`](./_template.md) when creating a new ADR. File naming:
`YYYY-MM-DD-kebab-slug.md`.

## Index

| Status | Date | Title | Tags |
|---|---|---|---|
| Accepted | 2026-06-04 | [Авторизация дашборда — пароль + сессия, HTTPS](./2026-06-04-dashboard-auth.md) | security, deployment |
| Accepted | 2026-06-04 | [Use Architecture Decision Records](./2026-06-04-use-adr.md) | meta |

<!--
Maintenance:
- Add every new ADR as a row above, latest first.
- When status changes (Accepted → Deprecated/Superseded), update the row and
  the ADR's Status field; never delete rows.
-->
