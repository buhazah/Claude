# Serene — Appointment Marketplace (UAE)

Production-grade Flutter + Firebase foundation for a UAE service
marketplace: customers discover businesses and book appointments in under
3 taps; owners run their business from a dedicated dashboard. **Salons are
the launch vertical** — the data model is vertical-agnostic (`businesses`
+ `category`), so expanding to spas, barbershops, clinics or fitness is a
new category value, not a migration.

## Features

**Customer**
- Phone-first auth (email + password reset optional), role-based onboarding
- Discovery home: nearby listings (distance-sorted, lazy list + load-more),
  category / gender / price / rating filters, "🔥 Hot deals" carousel
- Business detail: gallery, rating, services with live-offer pricing
- 3-tap booking: **Book** → pick a slot → **Confirm** — capacity-aware
  availability, offer discounts applied and snapshotted atomically
- Booking history with cancellation

**Owner**
- Guided business setup (multi-branch supported, branch switcher)
- Dashboard: today's schedule, pending requests, revenue snapshot,
  listing-approval status
- Services CRUD (price + duration), bookable capacity units
  (chairs / rooms / staff), weekly hours + blocked slots
- Booking inbox (accept / reject with validated transitions), day schedule
- Offers: % discounts with validity period, optional **daily happy-hour
  window** (e.g. 3–6 PM), redemption caps

## Architecture

Feature-based clean architecture; strict layer direction
(presentation → domain ← data). See `docs/CONVENTIONS.md` for the naming
and mapping rules.

```
lib/
├── core/                          # constants, di, errors, router,
│                                  #   theme, utils (Money!), widgets
└── features/<feature>/
    ├── domain/                    # entities, repository interfaces,
    │                              #   pure services (unit-tested)
    ├── data/                      # Firestore DTOs + repository impls
    └── presentation/              # Riverpod providers/controllers, UI
```

- **State/DI:** Riverpod. **Routing:** go_router with one role-based
  redirect. **Money:** integer fils (`Money`) end-to-end — no doubles.
- **Pure domain services:** `SlotGenerator` (working hours × capacity ×
  busy slots × blocked slots) and `OfferPricing` — exhaustively tested in
  `test/`.

## Firestore data model

| Collection | Key fields |
|---|---|
| `users` | name, phone, email, role (`customer`/`owner`) |
| `businesses` | ownerId, name, location, images[], rating, ratingCount, audience, **category**, **approved**, startingPriceFils, workingHours |
| `businesses/{id}/resources` | name — bookable capacity units |
| `businesses/{id}/blockedSlots` | start, end — owner blocks (public, no notes) |
| `businesses/{id}/busySlots` | start, end, bookingId — **public availability projection** (no customer data) |
| `services` | businessId, name, priceFils, durationMinutes |
| `bookings` | userId, businessId, **ownerId**, serviceId, dateTime, status, priceFils, originalPriceFils, offerId + display snapshots |
| `offers` | businessId, title, discountPercent, startTime, endTime, dailyStartMinute?, dailyEndMinute?, active, maxRedemptions, redemptionCount |

**Key integrity properties** (enforced in `firebase/firestore.rules`):
- Booking documents are private (customer + owner); availability is
  computed from the public times-only `busySlots` projection.
- Bookings, their busy slot, and offer redemption are one atomic batch.
- Booking status transitions are validated (no cancelled→confirmed).
- `approved`, `rating`, `ownerId` are never client-writable — listings go
  live only after admin approval (see `docs/MIGRATION.md`).

## Getting started

```bash
cd salon_booking_app
flutter create --platforms android,ios --org com.yourcompany .
dart pub global activate flutterfire_cli
flutterfire configure                       # writes lib/firebase_options.dart

# Firebase console: enable Auth (Phone + Email/Password), Firestore, Storage.
firebase deploy --only firestore:rules,firestore:indexes,storage
# Optional server-side hardening:
cd firebase/functions && npm install && cd ../..
firebase deploy --only functions

flutter pub get && flutter run
```

New listings need admin approval to appear in discovery — flip
`businesses/{id}.approved` to `true` in the console during development.

### Tests

```bash
flutter test   # slot generation (capacity), offer pricing, Money
```

## Scaling roadmap

Done in this codebase: vertical-agnostic model, capacity/resources,
integer-fils money, validated transitions, atomic booking batch, lazy
discovery with load-more, multi-branch owners, recurring offer windows.

Next: transactional slot lock + notifications in Cloud Functions (hooks
ready), i18n/Arabic RTL (see conventions doc), geohash discovery, image
uploads, reviews write-path, payments.
