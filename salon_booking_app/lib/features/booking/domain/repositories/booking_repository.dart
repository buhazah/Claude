import '../entities/booking.dart';

/// Contract for booking persistence and status transitions.
abstract interface class BookingRepository {
  /// Creates a booking with status `pending`, guarding against
  /// double-booking of the same slot. Returns the new booking id.
  /// Throws [SlotUnavailableException] on conflict.
  Future<String> createBooking(Booking booking);

  /// Customer's bookings, newest first.
  Stream<List<Booking>> watchUserBookings(String userId);

  /// All bookings of a salon on [day] (owner schedule + slot generation).
  Stream<List<Booking>> watchSalonBookingsForDay(String salonId, DateTime day);

  /// A salon's bookings filtered by status, soonest first (owner inbox).
  Stream<List<Booking>> watchSalonBookingsByStatus(
    String salonId,
    BookingStatus status,
  );

  Future<void> updateStatus(String bookingId, BookingStatus status);
}
