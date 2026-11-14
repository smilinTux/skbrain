---
id: service-<slug>
type: service
namespace: ops
lifecycle: draft
title: <the service, one line>
tags: [<free topic tags>]
edges:
  - {target: node-<slug>, type: runs_on}
state_refs:
  actions: [<operator-standard-action-name>]
created: YYYY-MM-DD
updated: YYYY-MM-DD
---

# service-<slug>

## Definition

- Host process or unit name, port, data path.
- Runs on [[node-<slug>]].

## Known errors and runbooks

- [[ke-<id>]] -> [[runbook-<slug>]].
