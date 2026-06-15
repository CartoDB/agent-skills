# Support Bundle Directory Structure

## Standard KOTS (GKE / AKS / EKS multi-node)

```
<bundle-root>/
├── analysis.json                                         # automated analyzer results
├── kots/
│   └── admin_console/
│       ├── app-info.json                                 # app_status, sequence, k8s version
│       ├── carto-self-hosted/
│       │   ├── kotsadm.log                               # DB migration / kotsadm ops log
│       │   ├── schemahero-apply.log                      # schema migration log
│       │   └── restore-db.log                            # present only if DB restore ran
├── replicated/
│   └── logs/
│       └── <pod>/
│           └── replicated.log                            # per-deployment ready/missing/unavailable states with timestamps
├── tenant-requirements-check/
│   └── tenant-requirements-check.log                     # JSON — per-check pass/fail, SA, buckets, Redis, PubSub, egress, certs
├── cluster-resources/
│   ├── pods/
│   │   └── carto-self-hosted.json                        # pod phase + container states
│   ├── deployments/
│   │   └── carto-self-hosted.json                        # desired/ready/available per deployment
│   ├── events/
│   │   └── carto-self-hosted.json                        # Warning + Normal events
│   └── configmaps/
│       └── carto-self-hosted.json                        # all ConfigMaps including carto-router
├── namespace-carto-self-hosted-logs/
│   └── <pod>/                                            # individual pod logs
└── registry/
    └── images.json                                       # expected images + exists: true/false
```

### Key files and what to look for

| File | Field / Pattern | What it means |
|---|---|---|
| `analysis.json` | `enable.debug.mode.for.carto.support` error | Debug mode off — logs are limited |
| `app-info.json` | `app_status: "missing"` | CARTO Deployments don't exist in the cluster |
| `app-info.json` | `app_status: "unavailable"` | Deployments exist but pods are not ready |
| `app-info.json` | `app_status: "degraded"` | Some pods running, some not |
| `tenant-requirements-check.log` | `ServiceAccountValidator` failed | SA lacks required IAM permissions |
| `cluster-resources/configmaps` | `carto-router` → `ROUTER_INGRESS_TESTING_MODE: "true"` | Ingress Testing Mode on — only router+valkey deploy |
| `cluster-resources/configmaps` | `kotsadm-config` → `initial-app-images-pushed: "false"` | KOTS gates Deployment creation until images are pushed |
| `registry/images.json` | any `exists: false` | Image not reachable — pods will fail to schedule |

### Redis vs Valkey

Older installs use `carto-redis-master-0`; newer ones use `carto-valkey`. Both are normal — adapt grep targets accordingly.

### Multiple namespaces

Some customers run prod + dev on the same cluster. Bundles may contain logs from both (e.g. `namespace-carto-logs` and `namespace-carto-dev-logs`). The deployments JSON covers one namespace at a time — confirm which namespace the issue is in before drawing conclusions.

---

## Embedded-Cluster (single-node, typically AWS)

Structure differs significantly from standard KOTS:

```
<bundle-root>/
├── analysis.json
├── kots/
│   └── admin_console/
│       └── app-info.json
├── namespace-kotsadm-logs/                               # CARTO pod logs here (NOT namespace-carto-self-hosted-logs)
├── cluster-resources/
│   ├── pods/
│   │   ├── kotsadm.json                                  # CARTO pods are in the kotsadm namespace
│   │   ├── default.json
│   │   └── <other-namespace>.json
│   ├── deployments/
│   │   ├── kotsadm.json                                  # Deployments split across per-namespace files
│   │   └── ...
│   └── events/
│       └── ...
├── k0scontroller/                                        # k0s control plane logs (infra only)
├── k0sworker/
├── local-artifact-mirror/
└── podlogs/                                              # infra-level pod logs
```

### Extra namespaces in embedded-cluster

| Namespace | Purpose |
|---|---|
| `seaweedfs` | Object storage (replaces GCS/S3) |
| `velero` | Backup |
| `openebs` | Block storage |

### Key differences from standard KOTS

- CARTO pods are in the `kotsadm` namespace, not `carto-self-hosted`.
- Pod logs are in `namespace-kotsadm-logs/`, not `namespace-carto-self-hosted-logs/`.
- Deployments are split across multiple per-namespace JSON files — iterate all files in `cluster-resources/deployments/`.
- Single node on AWS is typical. Node pressure (CPU/mem/disk) is more likely to be a factor.
