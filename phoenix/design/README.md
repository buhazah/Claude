# Phoenix — Founder Command Center, design

**Status: design complete, awaiting review. Nothing is implemented.**

| | |
|---|---|
| [`phoenix-command-center.html`](phoenix-command-center.html) | The prototype. Seven navigable screens: five operating surfaces, the design system, the architecture |
| [`tokens/tokens.css`](tokens/tokens.css) | Colour, type and layout tokens, both themes |

Published for review at the artifact URL in the conversation. Open it, click
through the rail, and toggle the theme.

## The design in three decisions

**The chrome carries the three zero-tolerance metrics.** Unauthorised actions,
unreconciled figures reported, account losses caused. `CHARTER.md §6` says those
are never averaged, never trended and never traded off against anything — so
they sit in a fixed strip that cannot be scrolled away from. It is the one
structural risk in the design and it is the one most true to the company.

**Every number is monospaced and tabular.** This is what separates an instrument
from a CRM. Columns align, digits do not reflow while you read them, and the
interface inherits the posture of the thing it is for — measurement someone else
can check.

**Customer words are set in the serif, with a rule. Our commentary is grey
sans.** Never the same treatment. The visual distinction is the discipline that
stops a paraphrase quietly becoming a quote, which is the failure the whole
discovery log exists to prevent.

## Palette and type, briefly

Cool graphite ground with a petrol accent — deliberately not the warm-cream and
terracotta, or the near-black with an acid pop, that this kind of page usually
defaults to. Semantic colour (critical, caution, verified) is separate from the
accent and appears nowhere else: a dashboard that borrows its alarm colour for
navigation teaches you to ignore the alarm.

Three faces, three jobs. Charter/Iowan serif for screen titles and verbatim
quotes; a system grotesque for interface prose, deliberately not Inter;
monospace for all figures. No webfont is linked — the artifact CSP blocks font
CDNs, and a silent fallback would be worse than a considered system stack.

## Claude Design

`DesignSync list_projects` returned nothing and `create_project` needs an
interactive permission grant this session cannot give. To push the component
library when you are at a terminal:

```
/design-sync            # creates the project, then syncs component by component
```

`tokens/tokens.css` is already in the shape that expects. Component previews get
extracted from the prototype during implementation rather than maintained twice.

## Scope note

Three of the five surfaces — Command, Clients, Effort — sit on data
`phoenix/ops` already produces and can be implemented now. **Audits** and
**Intelligence** need objects that do not exist yet (`Audit`, `Stage`,
`Hypothesis`); they are designed here so Phase B has a target, and implementing
them against invented data is how a design starts lying about the product.

Implementation order is on the Architecture screen.
