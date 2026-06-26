# Component Spec

Generate a complete implementation spec for a UI component from a description or screenshot.

Produce the following sections:

## Purpose
One sentence: what problem this component solves for the user.

## Props / API
Table of all props with name, type, default, required flag, and description.

## States
Enumerate every visual and functional state: default, hover, focus, active, disabled, loading, error, empty, success.

## Accessibility
- ARIA role and required attributes
- Keyboard interactions (Tab, Enter, Space, Escape, Arrow keys)
- Screen reader announcements for dynamic changes
- Required contrast ratio for key elements

## Responsive behaviour
How the component adapts at sm / md / lg / xl breakpoints.

## Design tokens used
List spacing, color, typography, and shadow tokens this component consumes.

## Edge cases
- Maximum content length
- Minimum/zero-item states
- RTL support considerations
- Long words / URLs that could break layout

## Example usage
Short JSX or HTML snippet showing the canonical usage.

---
Ask clarifying questions if the description is ambiguous before generating the spec.
