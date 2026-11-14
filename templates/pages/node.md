---
id: node-<slug>
type: node
namespace: ops
lifecycle: draft
title: <the node, one line>
tags: [node]
edges:
  - {target: node-<other>, type: connects_to}
state_refs:
  actions: []
created: YYYY-MM-DD
updated: YYYY-MM-DD
---

# node-<slug>

Role of this node, what runs on it, and links to its build and restore
procedures. Never secrets: credentials live in the secret vault.

## Runbooks that touch this node

- [[runbook-<slug>]]
