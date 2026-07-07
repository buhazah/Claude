import 'package:cloud_firestore/cloud_firestore.dart';

import '../../../../core/constants/firestore_collections.dart';
import '../../../../core/errors/app_exception.dart';
import '../../domain/entities/booking.dart';
import '../../domain/repositories/booking_repository.dart';
import '../models/booking_model.dart';

/// Firestore-backed [BookingRepository].
class FirestoreBookingRepository implements BookingRepository {
  FirestoreBookingRepository({required FirebaseFirestore firestore})
      : _firestore = firestore;

  final FirebaseFirestore _firestore;

  CollectionReference<Map<String, dynamic>> get _bookings =>
      _firestore.collection(FirestoreCollections.bookings);

  @override
  Future<String> createBooking(Booking booking) async {
    try {
      // Conflict guard: re-check the salon's bookings around the requested
      // window right before writing. A malicious client can bypass this
      // (it's a query, not a transaction over the range) — the server-side
      // slot lock is a planned Cloud Function; for the MVP this closes the
      // realistic "two customers picked the same slot" race window.
      final windowStart = booking.start.subtract(const Duration(hours: 3));
      final conflictCheck = await _bookings
          .where('salonId', isEqualTo: booking.salonId)
          .where('dateTime',
              isGreaterThanOrEqualTo: Timestamp.fromDate(windowStart))
          .where('dateTime',
              isLessThan: Timestamp.fromDate(booking.end))
          .get();

      final clash = conflictCheck.docs.map(BookingModel.fromDoc).any(
            (existing) =>
                existing.status.blocksSlot &&
                existing.start.isBefore(booking.end) &&
                existing.end.isAfter(booking.start),
          );
      if (clash) throw const SlotUnavailableException();

      final doc = await _bookings.add(BookingModel.toMap(booking));
      return doc.id;
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
  Stream<List<Booking>> watchSalonBookingsForDay(
    String salonId,
    DateTime day,
  ) {
    final dayStart = DateTime(day.year, day.month, day.day);
    final dayEnd = dayStart.add(const Duration(days: 1));
    return _bookings
        .where('salonId', isEqualTo: salonId)
        .where('dateTime',
            isGreaterThanOrEqualTo: Timestamp.fromDate(dayStart))
        .where('dateTime', isLessThan: Timestamp.fromDate(dayEnd))
        .orderBy('dateTime')
        .snapshots()
        .map((snap) => snap.docs.map(BookingModel.fromDoc).toList());
  }

  @override
  Stream<List<Booking>> watchSalonBookingsByStatus(
    String salonId,
    BookingStatus status,
  ) =>
      _bookings
          .where('salonId', isEqualTo: salonId)
          .where('status', isEqualTo: status.value)
          .orderBy('dateTime')
          .limit(100)
          .snapshots()
          .map((snap) => snap.docs.map(BookingModel.fromDoc).toList());

  @override
  Future<void> updateStatus(String bookingId, BookingStatus status) async {
    try {
      await _bookings.doc(bookingId).update(<String, dynamic>{
        'status': status.value,
        'updatedAt': FieldValue.serverTimestamp(),
      });
    } on FirebaseException catch (e) {
      throw DataException(e.message ?? 'Could not update the booking.');
    }
  }
}
