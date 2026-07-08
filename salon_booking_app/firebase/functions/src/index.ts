/**
 * Cloud Functions — server-side integrity for the marketplace.
 *
 * Deployed functions:
 *  - onServiceWritten: keeps `businesses/{id}.startingPriceFils` in sync
 *    with the cheapest service (authoritative version of the client-side
 *    sync, which writes the same value).
 *  - onBookingStatusChanged: frees the public busy slot when a booking is
 *    cancelled (belt-and-braces for the client batch), and is the hook for
 *    FCM notifications once device tokens are collected.
 *  - sweepExpiredOffers: hourly job flipping `active=false` on offers past
 *    their end time, so stale offers stop matching the discovery query.
 */
import { initializeApp } from 'firebase-admin/app';
import { getFirestore } from 'firebase-admin/firestore';
import {
  onDocumentUpdated,
  onDocumentWritten,
} from 'firebase-functions/v2/firestore';
import { onSchedule } from 'firebase-functions/v2/scheduler';

initializeApp();
const db = getFirestore();

export const onServiceWritten = onDocumentWritten(
  'services/{serviceId}',
  async (event) => {
    const businessId = (event.data?.after.exists
      ? event.data.after.data()?.businessId
      : event.data?.before.data()?.businessId) as string | undefined;
    if (!businessId) return;

    const cheapest = await db
      .collection('services')
      .where('businessId', '==', businessId)
      .orderBy('priceFils')
      .limit(1)
      .get();
    const startingPriceFils = cheapest.empty
      ? 0
      : (cheapest.docs[0].data().priceFils as number) ?? 0;

    await db
      .collection('businesses')
      .doc(businessId)
      .update({ startingPriceFils });
  },
);

export const onBookingStatusChanged = onDocumentUpdated(
  'bookings/{bookingId}',
  async (event) => {
    const before = event.data?.before.data();
    const after = event.data?.after.data();
    if (!before || !after || before.status === after.status) return;

    if (after.status === 'cancelled') {
      const businessId = after.businessId as string | undefined;
      if (businessId) {
        await db
          .collection('businesses')
          .doc(businessId)
          .collection('busySlots')
          .doc(event.params.bookingId)
          .delete()
          .catch(() => undefined); // already freed by the client batch
      }
    }

    // FCM hook: when users/{uid}.fcmToken is collected client-side
    // (see lib/core/services/push_notifications_service.dart), notify the
    // customer on confirmed/cancelled and the owner on new pending here.
  },
);

export const sweepExpiredOffers = onSchedule('every 60 minutes', async () => {
  const now = new Date();
  const expired = await db
    .collection('offers')
    .where('active', '==', true)
    .where('endTime', '<', now)
    .limit(200)
    .get();
  if (expired.empty) return;

  const batch = db.batch();
  for (const doc of expired.docs) {
    batch.update(doc.ref, { active: false });
  }
  await batch.commit();
});
