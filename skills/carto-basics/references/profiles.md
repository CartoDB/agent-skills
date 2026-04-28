# Profiles

Profiles let one machine hold credentials for multiple CARTO orgs (e.g. `dev`, `prod`, a customer org). Every command takes `--profile <name>`; the absence of the flag uses the default profile.

## Listing and switching

```bash
carto auth status                         # shows all profiles + which is default
carto auth use prod                       # switch default to "prod"
```

## Adding a new profile

A profile is created by logging in with a name:

```bash
carto auth login dev                      # creates "dev" profile
carto auth login prod                     # creates "prod" profile
carto auth use dev                        # set "dev" as default
```

## Removing a profile

```bash
carto auth logout dev                     # clears "dev" credentials
```

## Per-command profile override

```bash
carto maps list --profile prod
carto maps copy <map-id> --source-profile dev --dest-profile prod
```

`maps copy` and `workflows copy` cross profiles by design — a map made in `dev` can be promoted to `prod` in one command, with optional connection re-mapping.

## Env var override

`CARTO_PROFILE=prod` selects the profile globally. Useful in CI:

```bash
CARTO_PROFILE=prod carto maps list
```
