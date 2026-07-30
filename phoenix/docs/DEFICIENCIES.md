# Deficiency register

The only way to unfreeze frozen architecture. Process in
[`10-VALIDATION.md §3`](10-VALIDATION.md).

**An entry needs all five fields.** A client *asking* for something does not
qualify — the bar is that its absence cost us something measurable.

**Three different clients logging the same gap unfreezes it automatically.**

---

## Open

*None yet. Expected to fill up — a register that stays empty for six months means
nobody is filing, not that the architecture was right.*

---

## Template

```markdown
### D-001 · <one-line summary>

- **Client:** <name>
- **Date:** <yyyy-mm-dd>
- **Incident:** What happened, one paragraph, specific.
- **Cost:** Renewal at risk / N unbilled hours / a wrong number reached them /
  an action we could not take. Quantified.
- **Workaround tried:** What we did instead, and why it was not enough.
  (Manual effort counts and is usually the right first answer.)
- **Smallest fix:** Often not the architectural one. Say both if they differ.
- **Frozen decision it touches:** ADR / document section.
- **Status:** open | workaround holding | unfrozen | declined
```

---

## Resolved

*None yet.*

---

## Declined

Entries that did not meet the bar, kept because the pattern is informative — a
gap declined three times is often a gap in the offer rather than in the code.

*None yet.*
