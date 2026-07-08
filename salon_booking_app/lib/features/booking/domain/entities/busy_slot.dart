import 'time_range.dart';

/// Public, privacy-minimized projection of a taken time slot.
///
/// Lives at `businesses/{businessId}/busySlots/{bookingId}` and carries
/// only times + the booking id — never customer data — so availability can
/// be computed by anyone while booking documents stay private.
///
/// Written atomically with its booking (same WriteBatch) and deleted when
/// the booking is cancelled/rejected.
class BusySlot {
  const BusySlot({
    required this.bookingId,
    required this.start,
    required this.end,
  });

  final String bookingId;
  final DateTime start;
  final DateTime end;

  TimeRange get range => TimeRange(start: start, end: end);
}
