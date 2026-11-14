---
schema: skrsi.lesson.v1
id: lesson-<slug>
type: lesson
title: <one line, 120 characters at most>
service: [<service-tag>]
tags: [<keys of skrsi lesson-tags-v1 only, one to five>]
class: <defect | efficiency | reliability | process>
evidence:
  - {kind: <pr | review | incident | problem | card | artifact | evaluation>, ref: "<commit-pinned ref>"}
rule: <One actionable sentence, 40 words at most.>
check: <the test, lint or doctor rule that enforces it, or "none yet">
status: proposed
visibility: private
namespace: ops
lifecycle: draft
edges:
  - {target: ke-<id>, type: remediates}
created: YYYY-MM-DD
updated: YYYY-MM-DD
---

# <title>

Why the rule exists and what it would have prevented. A lesson page carries
exactly the skrsi `lesson-v1` fields plus the canon envelope, and no
`recurrence` or `origin` field.
