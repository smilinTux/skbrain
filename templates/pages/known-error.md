---
id: ke-<id>
type: known-error
namespace: ops
lifecycle: draft
title: <the symptom in one line>
tags: [<free topic tags>]
edges:
  - {target: service-<slug>, type: touches}
  - {target: node-<slug>, type: touches}
state_refs:
  kedb: ke-<id>
  actions: [<operator-standard-action-name>]
created: YYYY-MM-DD
updated: YYYY-MM-DD
---

# ke-<id>: <title>

## Symptoms

- What an operator or an alert sees.

## Root cause

What is actually wrong.

## Workaround

The steps, or a link: [[runbook-<slug>]].

## Permanent fix status

What would remove the cause, and whether anyone owns it.

## Links

Remediated by [[runbook-<slug>]]. Affects [[service-<slug>]].
