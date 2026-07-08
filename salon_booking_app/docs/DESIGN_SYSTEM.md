# Serene Design System

Premium marketplace foundation for the Serene app (salons today; spas,
clinics and other appointment businesses next). Design DNA: **Airbnb**
discovery cards, **Uber** flow simplicity, **Apple** restraint, **Stripe**
typographic professionalism.

```dart
import 'package:salon_booking_app/core/design_system/design_system.dart';
```

Everything lives under `lib/core/design_system/`:

```
design_system/
├── design_system.dart      # barrel — the only import screens need
├── tokens/                 # colors, typography, spacing, radius, shadows, motion
├── theme/app_theme.dart    # ThemeData light + dark, built from tokens
└── components/             # 12 reusable components
```

Legacy paths (`core/theme/*`, `PrimaryButton`, `RatingBadge`, `EmptyState`,
`showAppSheet`) forward to the system, so nothing broke — but new code
uses the design-system names directly.

---

## 1 · Color (`AppColors`, `AppColorsDark`)

| Token | Light | Role |
|---|---|---|
| `primary` | `#6C4AB6` | Brand violet — every primary CTA |
| `primaryDark` | `#4B2E92` | Pressed states, gradients, text-on-subtle |
| `primarySubtle` | `#F0EBFA` | Selected chips, icon plates |
| `accent` | `#E8B86D` | Gold garnish — deal badges, stars. Never a CTA |
| `background` | `#F8F7FB` | Scaffold (violet-tinted, never pure grey) |
| `surface` / `surfaceAlt` | `#FFFFFF` / `#F1EFF7` | Cards / nested fills |
| `border` | `#E8E5F0` | Hairlines, outlines |
| `textPrimary/Secondary/Tertiary` | `#1D1B26` / `#6E6A7C` / `#9A95A8` | 3-step text ramp |
| `success/warning/danger/info` | — | State only, never decoration |
| `statusPending/Confirmed/Cancelled/Completed` | — | Booking chips |

**Rules:** no inline hex in screens; one loud element per view (the offer
card owns the gradient); semantic colors never used for branding.

## 2 · Typography (`AppTypography`)

Platform face (SF Pro / Roboto) tuned — swap in a brand font later via
one `fontFamily` in `AppTheme` only.

| Token | Spec | Use |
|---|---|---|
| `display` | 32 / w800 / −0.6 | Onboarding, confirmations |
| `headline` | 24 / w800 / −0.4 | Screen titles |
| `title` | 18 / w700 / −0.2 | Section titles, sheet titles |
| `subtitle` | 15 / w600 | Card titles |
| `body` / `bodyStrong` / `bodyMuted` | 14 | Copy / emphasis / secondary |
| `caption` | 12 | Metadata |
| `label` | 11 / w700 / +1.1 tracking | UPPERCASE micro-labels |
| `price`, `priceSmall`, `priceStruck` | tabular figures | All money |

**Rules:** digits in columns always use tabular figures; hierarchy via
weight/size, never color alone.

## 3 · Spacing (`AppSpacing`)

Strict 4pt grid: `xxs 2 · xs 4 · sm 8 · md 12 · lg 16 · xl 20 · xxl 24 ·
xxxl 32 · huge 40`. Standard gutters: `screenPadding` (20 h),
`cardPadding` (16), `sheetPadding`. Gap widgets (`gapSm`…`gapXxl`) for
gap-based layout — no per-child margins, no magic numbers.

## 4 · Radius (`AppRadius`)

Tier ↔ component class, never mixed inside one component:
`badge 8 · chip 10 · control 12 (buttons) · field 14 (inputs) · card 16 ·
sheet 24 (top) · pill 999`.

## 5 · Shadows (`AppShadows`)

Soft, ink-tinted, layered: `soft` (nested lift) · `card` (two faint layers
— resting cards) · `floating` (FAB / sticky bars, violet-tinted) · `modal`
(sheets). **Rule:** border *or* shadow per component, never both.

## 6 · Motion (`AppMotion`)

Calm and immediate: `instant 100 · fast 150 (state) · base 250 (entrance)
· page 300 · slow 400`; curves `standard` (easeOutCubic), `emphasized`,
`exit`. Entrances fade + translate ≤ 16px; list stagger 40ms capped at ~6
items; the skeleton pulse (1100ms) is the only looping animation; every
animated component must respect `MediaQuery.disableAnimations` (the
skeleton already does).

## 7 · Components

All components are **entity-agnostic** — they take display primitives, and
feature widgets adapt domain entities to them. That keeps the design
system importable from anywhere without domain coupling.

| Component | Purpose / key API |
|---|---|
| `AppButton` | 4 variants (`primary/secondary/ghost/danger`) × 3 sizes, built-in `loading`. One primary per region; destructive = `danger` |
| `AppBusinessCard` | Discovery card: image (or branded fallback), name, `AppRatingBadge`, tag, distance, price-from, optional image `badge` |
| `AppServiceCard` | Service row: price + struck original + duration + one action (or custom `trailing` for owner edit/delete) |
| `AppOfferCard` | Gradient hot-deal card: `discountLabel`, title, business, `untilLabel` |
| `AppRatingBadge` | Star + one-decimal score (+count); `compact` for dense rows |
| `AppSearchBar` | Rounded field, auto clear button, owns controller if none given; debounce in providers, not here |
| `AppFilterChip` | Animated selected state (fill+border, no size change) |
| `AppBookingTimeline` | Vertical lifecycle: `complete ✓ / active ◉ / upcoming ○ / cancelled ✕` nodes — state encoded in form, not just color |
| `showAppBottomSheet` | The only way to open a modal sheet: rounded top, handle, title, keyboard-aware |
| `AppEmptyState` | Icon plate + title ("the situation") + message ("what to do") + optional action |
| `AppErrorState` | Failure + Retry; pass messages through `errorText()` first |
| `AppSkeleton` / `AppSkeletonCard` / `AppSkeletonList` | Pulse-based loading placeholders matching card silhouettes; zero dependencies |

## 8 · Theme

`AppTheme.light()` and `AppTheme.dark()` are both generated from tokens
(buttons, inputs, chips, nav, sheets, dialogs, tabs, snackbars, FAB).

### Dark mode

`darkTheme` is wired in `app.dart` but `themeMode` is pinned to light:
screens still reference static light tokens directly. The migration recipe
(screen-redesign phase): replace direct `AppColors.x` reads in screens with
`Theme.of(context)` / component usage, then flip to `ThemeMode.system`.
Components added from now on must be theme-driven so they inherit dark
support for free.

## Definition of done for new UI

1. No inline hex, no magic numbers — tokens only.
2. Loading = skeletons (not bare spinners) on list/card screens.
3. Empty and error states designed, with an action where one exists.
4. Digits tabular; prices via `price*` styles.
5. Animations within `AppMotion` durations; reduced-motion respected.
6. Component reused or added to the system — never forked into a feature.
