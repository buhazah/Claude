import '../../../../core/utils/money.dart';

enum BookingStatus {
  pending('pending'),
  confirmed('confirmed'),
  cancelled('cancelled'),
  completed('completed');

  const BookingStatus(this.value);

  /// Value persisted in Firestore (`bookings.status`).
  final String value;

  static BookingStatus parse(String? raw) => BookingStatus.values.firstWhere(
        (s) => s.value == raw,
        orElse: () => BookingStatus.pending,
      );

  String get label => switch (this) {
        BookingStatus.pending => 'Pending',
        BookingStatus.confirmed => 'Confirmed',
        BookingStatus.cancelled => 'Cancelled',
        BookingStatus.completed => 'Completed',
      };

  /// Statuses that occupy capacity on the business calendar.
  bool get blocksSlot =>
      this == BookingStatus.pending || this == BookingStatus.confirmed;
}

/// Domain booking. Service name/price/duration are snapshotted at booking
/// time so history stays correct if the business later edits the service.
///
/// Carries `ownerId` (denormalized from the business) so owner-side reads
/// are authorized directly by security rules — no per-document lookups.
class Booking {
  const Booking({
    required this.id,
    required this.userId,
    required this.customerName,
    required this.businessId,
    required this.businessName,
    required this.ownerId,
    required this.serviceId,
    required this.serviceName,
    required this.price,
    required this.originalPrice,
    required this.durationMinutes,
    required this.start,
    required this.status,
    required this.createdAt,
    this.offerId,
  });

  final String id;
  final String userId;
  final String customerName;
  final String businessId;
  final String businessName;
  final String ownerId;
  final String serviceId;
  final String serviceName;

  /// Final price after any offer discount.
  final Money price;
  final Money originalPrice;
  final int durationMinutes;
  final DateTime start;
  final BookingStatus status;
  final DateTime createdAt;

  /// Set when an offer discount was applied.
  final String? offerId;

  DateTime get end => start.add(Duration(minutes: durationMinutes));
  bool get hasDiscount => price < originalPrice;

  bool get isCancellableByCustomer =>
      status.blocksSlot && start.isAfter(DateTime.now());
}
