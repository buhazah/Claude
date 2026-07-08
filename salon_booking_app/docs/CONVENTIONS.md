# Code & Data Conventions

## Domain naming

- The marketplace entity is a **Business** (`businesses` collection). The
  vertical (salon, spa, clinic…) is the `category` field — never a new
  collection or a new entity type. UI copy may say "salon" while the
  launch vertical is salons; code and data never do.
- A bookable catalog item is a **ServiceOffering** (`services` collection).
- Capacity units (chairs / rooms / staff) are **BookableResource**s
  (`businesses/{id}/resources`). The MVP treats them as interchangeable
  capacity; per-staff booking becomes a UI feature later.

## Firestore mapping rule

**Field names match entity property names exactly** — `durationMinutes`,
`discountPercent`, `priceFils`, `audience`, `businessId`. No abbreviation
drift between the DTO and the domain. DTO mapping lives only in
`features/<x>/data/models/*_model.dart`.

## Money

All prices are `Money` (integer fils, 1 AED = 100 fils) — `double` prices
are forbidden past the UI edge. Firestore fields carry the `Fils` suffix
(`priceFils`, `startingPriceFils`).

## Layering

`presentation → domain ← data`. Firebase types never leave `data/`.
Controllers surface only `AppException` messages to the UI via
`errorText()` — raw `toString()` of unknown errors must not reach users.

## Privacy projections

Anything customers need for availability lives in public, minimized
subcollections (`busySlots`: start/end/bookingId only; `blockedSlots`:
start/end only — deliberately no free-text notes). Booking documents stay
private to customer + owner.

## State copyWith

Nullable state fields use the `_unset` sentinel pattern so `copyWith` can
distinguish "not passed" from "set to null" (see `AuthFlowState`,
`BookingFlowState`).

## Strings

Customer-visible copy currently lives inline in widgets in English.
Localization (en + ar, RTL) is the next scheduled infrastructure pass —
when adding screens, keep strings simple and sentence-level so extraction
to ARB is mechanical.
