---
id: runbook-<slug>
type: runbook
namespace: ops
lifecycle: draft
title: <imperative one line, for example "Restart the widget bridge">
tags: [<free topic tags>]
edges:
  - {target: ke-<id>, type: remediates}
  - {target: service-<slug>, type: touches}
  - {target: node-<slug>, type: touches}
state_refs:
  kedb: ke-<id>
  actions: [<operator-standard-action-name>]
created: YYYY-MM-DD
updated: YYYY-MM-DD
---

# <title>

One paragraph: what this recovers and which known error it remediates
([[ke-<id>]]).

## Preconditions

- What must be true before you start (freeze state, which condition is red).

## Steps

1. Numbered, copy-paste commands grounded in real units and paths.
2. Reference secrets by vault entry name, never by value.

## Verify

The command whose output proves it worked.

## Rollback

How to undo, or "Idempotent; nothing to undo."

## Escalate

When to stop and who to raise it with.
