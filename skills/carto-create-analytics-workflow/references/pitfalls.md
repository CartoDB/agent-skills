# Workflow Authoring Pitfalls

Cross-cutting guidance that doesn't belong on a single component. Component-specific gotchas are served by `carto workflows components get <names> --connection <conn> --json` (`notes` array) and `--input-formats --json` (input-type `pitfalls`) — fetch them when designing a workflow rather than memorising them.

---

## Native-first violations

`native.customsql` is the failure surface of the workflow. Most "I'll just write SQL" instincts have a native equivalent — see the [Native-first table in SKILL.md](../SKILL.md#native-first-rule). Signals you're reaching for customsql too early:

- The customsql is just a `WHERE` clause, a single `JOIN`, a `GROUP BY` with one or two aggregates, or a column projection.
- It wraps a single warehouse function (`ST_BUFFER`, `H3_FROMGEOGPOINT`, etc.) for which a dedicated native exists.
- Its only purpose is to rename or re-cast columns — use `native.selectexpression`.
- You're chaining customsql outputs through more customsql nodes — chain natives instead.

When customsql is the right call, the per-warehouse design footguns live in the matching provider doc:
- BigQuery: [providers/bigquery.md → `native.customsql` footguns](providers/bigquery.md#nativecustomsql-footguns-on-bigquery).
- Snowflake / Databricks: see the relevant `providers/*.md` for column-casing and identifier-quoting rules.

---

## `connectionProvider` mismatch

The `config.connectionProvider` value must match the actual provider of the connection used for validation/execution. Mismatches cause SQL generation to use the wrong dialect — generated SQL looks superficially valid but errors at runtime. Confirm with:

```bash
carto connections list --search <name> --json
```

(`carto connections get` requires a UUID, not a name.)
