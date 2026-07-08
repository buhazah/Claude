import '../entities/booking.dart';
import '../entities/busy_slot.dart';

/// Contract for booking persistence and status transitions.
abstract interface class BookingRepository {
  /// Creates a booking (status `pending`) atomically with its public busy
  /// slot, guarding against overbooking given the business [capacity].
  /// When [redeemOfferId] is set, the offer's redemption counter is
  /// incremented in the same atomic batch.
  ///
  /// Throws [SlotUnavailableException] when the slot filled up between
  /// selection and confirmation. Returns the new booking id.
  Future<String> createBooking(
    Booking booking, {
    required int capacity,
    String? redeemOfferId,
  });

  /// Customer's bookings, newest first.
  Stream<List<Booking>> watchUserBookings(String userId);

  /// Public busy slots of a business on [day] (drives slot generation for
  /// customers — booking documents themselves stay private).
  Stream<List<BusySlot>> watchBusySlots(String businessId, DateTime day);

  /// Owner schedule: the business's bookings on [day]. [ownerId] is part of
  /// the query so security rules can authorize the list read directly.
  Stream<List<Booking>> watchOwnerBookingsForDay({
    required String ownerId,
    required String businessId,
    required DateTime day,
  });

  /// Owner inbox: the business's bookings in [status], soonest first.
  Stream<List<Booking>> watchOwnerBookingsByStatus({
    required String ownerId,
    required String businessId,
    required BookingStatus status,
  });

  /// Applies a status transition. Cancelling also frees the public busy
  /// slot in the same atomic batch.
  Future<void> updateStatus(String bookingId, BookingStatus status);
}
