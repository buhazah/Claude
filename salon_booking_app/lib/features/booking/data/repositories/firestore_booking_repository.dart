import 'package:cloud_firestore/cloud_firestore.dart';

import '../../../../core/constants/firestore_collections.dart';
import '../../../../core/errors/app_exception.dart';
import '../../domain/entities/booking.dart';
import '../../domain/entities/busy_slot.dart';
import '../../domain/repositories/booking_repository.dart';
import '../models/booking_model.dart';

/// Firestore-backed [BookingRepository].
///
/// Availability is public via the `busySlots` projection (times only);
/// booking documents stay private to the customer + business owner.
class FirestoreBookingRepository implements BookingRepository {
  FirestoreBookingRepository({required FirebaseFirestore firestore})
      : _firestore = firestore;

  final FirebaseFirestore _firestore;

  CollectionReference<Map<String, dynamic>> get _bookings =>
      _firestore.collection(FirestoreCollections.bookings);

  CollectionReference<Map<String, dynamic>> _busySlots(String businessId) =>
      _firestore
          .collection(FirestoreCollections.businesses)
          .doc(businessId)
          .collection(FirestoreCollections.busySlots);

  @override
  Future<String> createBooking(
    Booking booking, {
    required int capacity,
    String? redeemOfferId,
  }) async {
    try {
      // Overbooking guard: re-count overlapping busy slots right before
      // writing. Concurrent writes can still race in a narrow window (a
      // client-side check, not a transaction over the range) — the
      // server-side lock is the Cloud Function hardening path; this closes
      // the realistic "two customers picked the last opening" case.
      final windowStart = booking.start.subtract(const Duration(hours: 8));
      final snapshot = await _busySlots(booking.businessId)
          .where('start',
              isGreaterThanOrEqualTo: Timestamp.fromDate(windowStart))
          .where('start', isLessThan: Timestamp.fromDate(booking.end))
          .get();

      final overlapping = snapshot.docs.where((doc) {
        final data = doc.data();
        final start = (data['start'] as Timestamp).toDate();
        final end = (data['end'] as Timestamp).toDate();
        return start.isBefore(booking.end) && end.isAfter(booking.start);
      }).length;
      if (overlapping >= capacity) throw const SlotUnavailableException();

      // Booking + its public busy slot (+ offer redemption) are one atomic
      // batch: they can never disagree.
      final bookingRef = _bookings.doc();
      final batch = _firestore.batch();
      batch.set(bookingRef, BookingModel.toMap(booking));
      batch.set(_busySlots(booking.businessId).doc(bookingRef.id),
          <String, dynamic>{
        'start': Timestamp.fromDate(booking.start),
        'end': Timestamp.fromDate(booking.end),
        'bookingId': bookingRef.id,
      });
      if (redeemOfferId != null) {
        batch.update(
          _firestore
              .collection(FirestoreCollections.offers)
              .doc(redeemOfferId),
          {'redemptionCount': FieldValue.increment(1)},
        );
      }
      await batch.commit();
      return bookingRef.id;
    } on FirebaseException catch (e) {
      throw DataException(e.message ?? 'Could not create the booking.');
    }
  }

  @override
  Stream<List<Booking>> watchUserBookings(String userId) => _bookings
      .where('userId', isEqualTo: userId)
      .orderBy('dateTime', descending: true)
      .limit(100)
      .snapshots()
      .map((snap) => snap.docs.map(BookingModel.fromDoc).toList());

  @override
  Stream<List<BusySlot>> watchBusySlots(String businessId, DateTime day) {
    final dayStart = DateTime(day.year, day.month, day.day);
    final dayEnd = dayStart.add(const Duration(days: 1));
    return _busySlots(businessId)
        .where('start', isGreaterThanOrEqualTo: Timestamp.fromDate(dayStart))
        .where('start', isLessThan: Timestamp.fromDate(dayEnd))
        .snapshots()
        .map(
          (snap) => snap.docs.map((doc) {
            final data = doc.data();
            return BusySlot(
              bookingId: (data['bookingId'] as String?) ?? doc.id,
              start: (data['start'] as Timestamp).toDate(),
              end: (data['end'] as Timestamp).toDate(),
            );
          }).toList(),
        );
  }

  @override
  Stream<List<Booking>> watchOwnerBookingsForDay({
    required String ownerId,
    required String businessId,
    required DateTime day,
  }) {
    final dayStart = DateTime(day.year, day.month, day.day);
    final dayEnd = dayStart.add(const Duration(days: 1));
    // ownerId is in the query so the rules' list authorization is provable
    // from the query constraints themselves.
    return _bookings
        .where('ownerId', isEqualTo: ownerId)
        .where('businessId', isEqualTo: businessId)
        .where('dateTime',
            isGreaterThanOrEqualTo: Timestamp.fromDate(dayStart))
        .where('dateTime', isLessThan: Timestamp.fromDate(dayEnd))
        .orderBy('dateTime')
        .snapshots()
        .map((snap) => snap.docs.map(BookingModel.fromDoc).toList());
  }

  @override
  Stream<List<Booking>> watchOwnerBookingsByStatus({
    required String ownerId,
    required String businessId,
    required BookingStatus status,
  }) =>
      _bookings
          .where('ownerId', isEqualTo: ownerId)
          .where('businessId', isEqualTo: businessId)
          .where('status', isEqualTo: status.value)
          .orderBy('dateTime')
          .limit(100)
          .snapshots()
          .map((snap) => snap.docs.map(BookingModel.fromDoc).toList());

  @override
  Future<void> updateStatus(String bookingId, BookingStatus status) async {
    try {
      final bookingSnap = await _bookings.doc(bookingId).get();
      final businessId =
          (bookingSnap.data()?['businessId'] as String?) ?? '';

      final batch = _firestore.batch();
      batch.update(_bookings.doc(bookingId), <String, dynamic>{
        'status': status.value,
        'updatedAt': FieldValue.serverTimestamp(),
      });
      // Cancelling frees the slot for other customers immediately.
      if (status == BookingStatus.cancelled && businessId.isNotEmpty) {
        batch.delete(_busySlots(businessId).doc(bookingId));
      }
      await batch.commit();
    } on FirebaseException catch (e) {
      throw DataException(e.message ?? 'Could not update the booking.');
    }
  }
}
