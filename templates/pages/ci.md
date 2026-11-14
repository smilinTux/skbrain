---
id: ci-<slug>
type: ci
namespace: ops
lifecycle: draft
title: <the configuration item, one line>
tags: [<free topic tags>]
edges:
  - {target: node-<slug>, type: runs_on}
  - {target: ci-<other>, type: depends_on}
state_refs:
  actions: []
created: YYYY-MM-DD
updated: YYYY-MM-DD
---

# ci-<slug>

The DEFINITION of this configuration item: intended type, owner and node,
intended relationships (`depends_on`, `runs_on`, `hosts`, `connects_to`),
intended key attributes (port, unit name, data path).

No live status here. Status is state, and state lives in the CMDB store, never
in git.

## Runbooks that touch this item

- [[runbook-<slug>]]
