/**
 * Cloud Functions entry point.
 *
 * The MVP runs entirely client-side against Firestore; this package exists so
 * server-side logic has a ready home as the marketplace grows. Planned
 * functions (uncomment / implement as each feature lands):
 *
 *  - onBookingCreated  → notify the salon owner via FCM.
 *  - onBookingStatusChanged → notify the customer (confirmed / cancelled).
 *  - onServiceWritten  → recompute the salon's denormalized `startingPrice`.
 *  - onReviewWritten   → recompute salon `rating` / `ratingCount` (future).
 *  - scheduled offer sweep → deactivate offers past `endTime`.
 */
import { initializeApp } from 'firebase-admin/app';

initializeApp();

// Example scaffold — kept commented until FCM tokens are collected client-side.
//
// import { onDocumentCreated } from 'firebase-functions/v2/firestore';
//
// export const onBookingCreated = onDocumentCreated(
//   'bookings/{bookingId}',
//   async (event) => {
//     // 1. Load salon owner's FCM token from users/{ownerId}.
//     // 2. Send "New booking request" notification.
//   },
// );

export {};
