# pos-rebuild change (mirror)

This directory mirrors the workspace change
`D:/sistema_web/openspec/changes/pos-rebuild/` so this repo can be opened in
isolation and still see the artifacts.

The authoritative copies live at the workspace root. Any change here is a
copy; if they diverge, the workspace version wins.

## Files

- `explore-report.md` — map of `Proyecto_A` (read-only reference).
- `proposal.md` — what and why.
- `spec.md` — contracts (REST, broker, state machine, rules, data).
- `design.md` — layer-by-layer implementation choices.
- `tasks.md` — ordered implementation checklist.

This repo (`sys_api`) implements the tasks tagged `[api]`. Sibling repos
implement the rest:

- `Proyecto_B/sys_invoice_check` — tasks tagged `[val]`.
- `Proyecto_B/sys_front` — tasks tagged `[fe]`.
- workspace root — tasks tagged `[cross]` and `[wf]`.
