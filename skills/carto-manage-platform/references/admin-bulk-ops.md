# Superadmin bulk operations

`carto admin *` commands operate **across the whole org**, ignoring per-user ownership. They require Superadmin role; regular Admins will see "permission denied".

## `admin list`

Cross-user listing of resources.

```bash
carto admin list <type> [options]
```

Types: `maps`, `workflows`, `connections`.

| Flag | Effect |
|---|---|
| `--all` | Fetch all pages. |
| `--page <n>` / `--page-size <n>` | Pagination. |
| `--search <query>` | Filter by text. |
| `--json` | Machine-readable. |

```bash
# Every map in the org
carto admin list maps --all --json

# Every workflow whose name contains "test"
carto admin list workflows --all --search "test" --json
```

Use `admin list` to *generate* the input list for `admin batch-delete` or `admin transfer`.

## `admin batch-delete`

Bulk delete. **Irreversible.** Reads a list of resource IDs (typically piped from `admin list`).

```bash
carto admin batch-delete
```

Interactive by default — prompts for the list of IDs. For automation, pipe / use `--file`:

```bash
# Generate the kill-list
carto admin list maps --all --search "test-" --json \
  | jq -r '.[].id' > to_delete.txt

# Inspect before destruction
wc -l to_delete.txt
head to_delete.txt

# Bulk delete
cat to_delete.txt | carto admin batch-delete --yes
```

Pass `--yes` to skip per-batch confirmation; the per-resource CARTO confirmation is also skipped under bulk.

**No undo.** Verify the list before piping.

## `admin transfer`

Transfer ownership of resources from one user to another — useful when a user leaves and their resources need to land with someone specific.

```bash
carto admin transfer
```

Interactive prompt for source user, destination user, and (optionally) which resource types. For automation, pass `--from`, `--to`, and `--type` flags:

```bash
carto admin transfer \
  --from alice@x.com \
  --to bob@x.com \
  --type maps
```

Variants by argument shape — check `carto admin transfer --help` if a flag isn't recognized.

`admin transfer` is preferred over deleting Alice's account when Bob needs visibility into Alice's history. `users delete` does an automatic transfer too (the receiver argument); use `admin transfer` when you want the transfer *without* deleting the source user.

## Safety patterns for bulk ops

1. **Always run `admin list` first**, save its output to a file, eyeball the count and a sample.
2. **Stage in dry-run** by piping `--json` through `jq` and checking the IDs match expectations.
3. **For `batch-delete`, prefer two passes**: filter by name → manually inspect → then delete. Don't compose `admin list | jq | batch-delete` in one chain unless you've reviewed the intermediate output.
4. **For `transfer`, do a small first batch** — transfer 5 resources, confirm the destination user can access them, then run the rest.
5. **Audit the result**: query `MapDeleted` / `MapTransferred` events in the activity log to confirm the intended outcome. See [`activity-event-reference.md`](activity-event-reference.md).

## Permission gotchas

- `admin batch-delete` returning "Forbidden" on an item usually means the resource is already deleted, *not* a permissions issue (Superadmin permissions are blanket).
- Cross-org transfers are not supported — `admin transfer` only moves within the current org. For cross-org, use `maps copy --dest-profile` / `workflows copy --dest-profile`.
