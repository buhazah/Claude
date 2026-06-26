# UI/UX Design Review

Review the current component or page for UI/UX quality, consistency, and user experience.

Evaluate across these dimensions:

**Visual consistency**
- Spacing: Are padding/margin values on-grid (consistent 4px/8px base)?
- Typography: Font sizes, weights, and line-heights from the design system?
- Color: Only tokens from the palette used? No hardcoded hex values?
- Border-radius, shadow, and elevation consistent with the system?

**Component design**
- Does the component do one thing well (single responsibility)?
- Are interactive states covered: default, hover, focus, active, disabled, loading, error?
- Empty state and edge cases (long strings, zero items, max content) handled?

**Responsiveness**
- Does layout adapt gracefully from 320px to 1440px+?
- Touch targets ≥ 44×44px on mobile?
- Text remains readable at all breakpoints (no overflow, truncation unintentional)?

**User experience**
- Is the primary action obvious and easy to reach?
- Feedback latency: Do async actions show loading and error states?
- Are destructive actions confirmed before executing?
- Copy is clear, actionable, and free of jargon?

Output a prioritized list of findings with specific line references and suggested fixes.
