# Accessibility Review

Review the current file or selected code for WCAG 2.1 AA accessibility issues.

Check for:
- Missing or incorrect ARIA roles, labels, and attributes (`aria-label`, `aria-describedby`, `role`)
- Images lacking meaningful `alt` text (decorative images should use `alt=""`)
- Interactive elements (buttons, links, inputs) without accessible names
- Color contrast issues — flag anything that relies solely on color to convey meaning
- Keyboard navigation gaps: focus order, missing `:focus` styles, focus traps
- Form inputs missing `<label>` associations (`for`/`id` or `aria-labelledby`)
- Heading hierarchy violations (skipped levels, non-semantic heading use)
- Dynamic content not announced to screen readers (missing live regions)
- Inaccessible modals or dialogs (missing `role="dialog"`, focus management, `aria-modal`)

Output format:
1. **Critical** — Blocks users with disabilities entirely
2. **Serious** — Major barriers; fix before shipping
3. **Moderate** — Friction for assistive tech users
4. **Minor** — Best-practice improvements

For each finding include the line reference, the specific WCAG criterion (e.g. 1.4.3 Contrast, 4.1.2 Name/Role/Value), and a concrete code fix.
