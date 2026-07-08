# Migration: salon-era schema → marketplace schema

The data model was generalized **before launch** precisely so no live-data
migration would ever be needed. If your Firebase project contains test
data written by the previous code (collections `salons`, fields `salonId`,
`type`, `price`, `duration`, `discount`), the cheapest path is a clean
slate:

1. Firebase console → Firestore → delete the `salons`, `services`,
   `bookings`, `offers` collections (test data only!).
2. Redeploy backend config:
   ```bash
   firebase deploy --only firestore:rules,firestore:indexes
   ```
3. Wait for the composite indexes to show **Enabled**, then run the app —
   it now writes the new schema (`businesses`, `businessId`, `audience`,
   `priceFils`, `durationMinutes`, `discountPercent`).

## Approving a listing

New businesses are created with `approved: false` and are invisible in
discovery until approved. To approve during development: Firestore console
→ `businesses/{id}` → set `approved` to `true`. (An admin tool / custom
claim flow replaces this before real onboarding.)

## Deploying Cloud Functions (optional but recommended)

```bash
cd firebase/functions && npm install
firebase deploy --only functions
```

Deploys: `onServiceWritten` (starting-price sync), `onBookingStatusChanged`
(busy-slot cleanup + notification hook), `sweepExpiredOffers` (hourly).
The app works without them; they harden integrity server-side.
