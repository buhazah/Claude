# Serene — Salon Booking Marketplace (UAE)

Production-grade Flutter + Firebase foundation for a salon booking
marketplace: customers discover salons and book appointments in under
3 taps; salon owners run their business from a dedicated dashboard.
Built as a startup MVP that can grow into a full SaaS marketplace
(payments, AI recommendations, subscriptions, multi-city).

## Features

**Customer**
- Phone-first auth (email optional), role-based onboarding
- Discovery home: nearby salons (distance-sorted), gender / price / rating
  filters, "🔥 Hot deals near you" carousel
- Salon detail: gallery, rating, services with live-offer pricing,
  opening hours-aware availability
- 3-tap booking: **Book** on a service → pick a slot → **Confirm**
  (offer discounts applied automatically and snapshotted)
- Booking history with cancellation

**Salon owner**
- Guided salon setup on first login
- Dashboard: today's schedule, pending requests, revenue snapshot
- Services: add / edit / delete with price + duration
- Bookings: accept / reject inbox, day-by-day schedule, mark completed
- Availability: weekly working hours + one-off blocked slots
- Offers: time-boxed % discounts with optional redemption caps

## Architecture

Feature-based clean architecture; strict layer direction
(presentation → domain ← data):

```
lib/
├── main.dart / app.dart          # bootstrap only
├── core/                         # cross-feature building blocks
│   ├── constants/                # app constants, Firestore names
│   ├── di/                       # Firebase SDK providers (Riverpod)
│   ├── errors/                   # typed AppException hierarchy
│   ├── router/                   # go_router + role-based redirects
│   ├── services/                 # FCM-ready push service
│   ├── theme/                    # Material 3 theme tokens
│   ├── utils/                    # formatters, geo helpers
│   └── widgets/                  # shared UI primitives
└── features/<feature>/
    ├── domain/                   # entities, repository interfaces,
    │                             #   pure business services (unit-tested)
    ├── data/                     # Firestore DTOs + repository impls
    └── presentation/             # providers, controllers, screens, widgets
```

- **State/DI:** Riverpod. Screens watch providers; controllers call
  repository *interfaces*; Firebase types never leak past `data/`.
- **Routing:** go_router with a single redirect driven by the live
  `users/{uid}` profile stream — signed-out → login, no role → onboarding,
  owner → dashboard shell, customer → discovery shell.
- **Business logic lives in `domain/services`** and is pure Dart:
  - `SlotGenerator` — working hours × existing bookings × blocked slots
    → bookable slots
  - `OfferPricing` — best live offer selection + discount math
- **Repository pattern** everywhere (`AuthRepository`, `SalonRepository`,
  `BookingRepository`, `OfferRepository`) so Firebase can be swapped or
  emulated in tests without touching UI.

## Firestore data model

| Collection | Key fields |
|---|---|
| `users` | name, phone, email, role (`customer`/`owner`), createdAt |
| `salons` | ownerId, name, location (GeoPoint), images[], rating, ratingCount, type (`male`/`female`/`both`), startingPrice*, workingHours, createdAt |
| `salons/{id}/blockedSlots` | start, end, reason |
| `services` | salonId, name, price, duration |
| `bookings` | userId, salonId, serviceId, dateTime, status (`pending`/`confirmed`/`cancelled`/`completed`), price, originalPrice, offerId, snapshots (serviceName, salonName, customerName) |
| `offers` | salonId, title, discount, startTime, endTime, active, maxRedemptions, redemptionCount |

\* denormalized min service price for cheap list filtering.

Security rules (`firebase/firestore.rules`) enforce: profiles are
self-only; salons/services/offers are public-read, owner-write; bookings
are visible to the customer + salon owner, created only as `pending`, and
updates are restricted to legal status transitions.

## Getting started

```bash
# 1. Generate platform folders (android/ios) — not committed:
cd salon_booking_app
flutter create --platforms android,ios --org com.yourcompany .

# 2. Connect your Firebase project (overwrites lib/firebase_options.dart):
dart pub global activate flutterfire_cli
flutterfire configure

# 3. In the Firebase console enable:
#    Authentication → Phone + Email/Password, Firestore, Storage.

# 4. Deploy rules & indexes:
firebase deploy --only firestore:rules,firestore:indexes,storage

# 5. Run
flutter pub get
flutter run
```

Local development against the emulator suite: `firebase emulators:start`
and point the SDK providers in `core/di/firebase_providers.dart` at the
emulators (`useAuthEmulator` / `useFirestoreEmulator`).

### Tests

```bash
flutter test   # slot generation + offer pricing domain suites
```

## Scaling roadmap (already accommodated)

- **Payments** — booking snapshots `price`/`originalPrice`; a
  `PaymentRepository` slots in beside `BookingRepository`.
- **Push notifications** — `core/services/push_notifications_service.dart`
  + commented Cloud Function triggers in `firebase/functions`.
- **AI recommendations** — discovery already flows through
  `nearbySalonsProvider`; swap the ranking source without UI changes.
- **Real geo queries** — replace the client-side haversine sort behind
  `SalonRepository.watchSalons` with geohash queries.
- **Multi-city** — `AppConstants.default*` location becomes a per-city
  config document; salons already store `city`.
- **Salon subscriptions** — add a `plans` collection + custom claims;
  rules are structured around `ownsSalon()` already.
