# Known Failure Patterns

## `app_status: missing` — Deployments absent

CARTO application Deployments don't exist in the cluster.

**Distinguish:**
- ConfigMaps present, Deployments absent → Helm rendered but Deployments were never created. Usually a pre-hook job failure or SA lacking permission to create Deployments.
- Only `carto-router` and `carto-valkey` running → app workloads never created. Common on first deploys where SA was not authorised or KOTS Advanced Config was not set.

**Check first:** `tenant-requirements-check.log` → `ServiceAccountValidator`. If passing but Deployments still absent, ask whether a custom SA was set in KOTS Advanced Config.

---

## Ingress Testing Mode — all app Deployments absent

**Symptom:** `app_status: missing`, only router + valkey pods exist, SA checks pass.

**Root cause:** `ROUTER_INGRESS_TESTING_MODE: "true"` in the `carto-router` ConfigMap. This is an Admin Console option intended for testing the ingress/routing layer only — it intentionally skips creating all CARTO application Deployments.

**How to spot it:** `cluster-resources/configmaps/carto-self-hosted.json` → `carto-router` data → `ROUTER_INGRESS_TESTING_MODE`.

**Fix:** Disable "Ingress Testing Mode" in the KOTS Admin Console Config section and redeploy.

**Real case:** Issue #9917 (STC/Masterworks, June 2026) — misleadingly looked like a fresh-install SA/registry problem.

---

## Duplicate license / InvalidSelfHostedInstanceId

**Symptom:** `app_status: unavailable`. Most deployments desired > 0 but ready = 0. Pods in CrashLoopBackOff.

**Error in pod logs:**
```
InvalidSelfHostedInstanceId: Another instance is already running with this CARTO Self-Hosted license
```

Visible in `namespace-carto-self-hosted-logs/` for: maps-api, workspace-api, sql-worker, cdn-invalidator-sub, workspace-subscriber.

**Root cause:** Single license used across two environments simultaneously (e.g. dev + prod), or an old instance was not deregistered before a redeploy.

**Fix:** Deregister / remove the old instance, or obtain a second license for the second environment.

---

## `initial-app-images-pushed: false` — KOTS gates Deployment creation

**Symptom:** ConfigMaps exist but Deployments were never created across multiple redeployments.

**How to spot it:** `cluster-resources/configmaps/carto-self-hosted.json` → `kotsadm-config` → `initial-app-images-pushed: "false"`.

**Meaning:** KOTS will not create Deployments until it considers the required images pushed to the registry. This flag stays `false` if the initial image push failed or was interrupted.

**Action:** Escalate to engineering. Include: bundle timestamps, KOTS sequence, which deployments are missing, and the `initial-app-images-pushed` flag value.

---

## SA-related failures (GCP)

`ServiceAccountValidator` in `tenant-requirements-check.log` will show which IAM roles/permissions are missing.

If `ServiceAccountValidator` passes but Deployments are still absent, ask the customer:
1. Is a custom SA configured in KOTS Advanced Config?
2. Does that SA have the required roles (Storage Admin, Pub/Sub Admin, etc.)?

---

## Known noise (safe to ignore or note without escalating)

| Pattern | Location | Action |
|---|---|---|
| `LaunchDarkly SDK key not found` | `tenant-requirements-check.log` | Non-critical. Feature flags not configured. Mention to customer but not blocking. |
| Redis `"client is closed"` | `tenant-requirements-check.log` | Often transient. Verify Redis/Valkey pod is healthy separately. |
| `send() failed (111: Connection refused) while logging to syslog, server: [::1]:5447` | router pod logs | Syslog configured but not running. Non-blocking. |
| `Possible EventEmitter memory leak detected. 11 close listeners added to [Socket]` | maps-api pod logs | Not crashing. Flag only if customer reports maps-api instability or memory issues. |

---

## What a healthy bundle looks like

- `app_status: ready`
- All deployments: desired = ready = available
- No unhealthy containers in pods JSON
- `tenant-requirements-check.log`: all validators passed (LaunchDarkly failure acceptable)
- `analysis.json`: only flag is debug mode warning (if debug mode is off)
- No Warning events related to pods or images

---

## Escalation triggers

Escalate to engineering when:
- ConfigMaps exist but Deployments are absent across multiple redeployments AND `initial-app-images-pushed: false` is present.
- A known pattern has been ruled out and the root cause is not identifiable from the bundle.

Include in escalation: bundle timestamps, KOTS sequence, which deployments are missing, the `initial-app-images-pushed` flag value, and a summary of what was already ruled out.
