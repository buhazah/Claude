import '../../../../core/constants/app_constants.dart';
import '../../../salons/domain/entities/blocked_slot.dart';
import '../../../salons/domain/entities/working_hours.dart';
import '../entities/booking.dart';
import '../entities/time_slot.dart';

/// Pure business logic: computes which slots a customer can book.
///
/// Inputs are plain domain objects, no Firebase/Flutter types — this is the
/// kind of logic that gets unit-tested exhaustively (see
/// test/booking/slot_generator_test.dart).
abstract final class SlotGenerator {
  /// Available slots on [day] for a service lasting [serviceDurationMinutes].
  ///
  /// A slot on the [AppConstants.slotGridMinutes] grid is offered when it:
  ///  * fits fully inside the salon's working hours for that weekday,
  ///  * doesn't overlap a pending/confirmed booking,
  ///  * doesn't overlap an owner-blocked range,
  ///  * starts in the future (for today).
  static List<TimeSlot> generate({
    required DateTime day,
    required int serviceDurationMinutes,
    required WeeklyHours workingHours,
    required List<Booking> existingBookings,
    required List<BlockedSlot> blockedSlots,
    DateTime? now,
  }) {
    final hours = workingHours.forWeekday(day.weekday);
    if (hours.closed || hours.closeMinutes <= hours.openMinutes) {
      return const [];
    }

    final clock = now ?? DateTime.now();
    final dayStart = DateTime(day.year, day.month, day.day);
    final occupied = existingBookings
        .where((b) => b.status.blocksSlot)
        .map((b) => (start: b.start, end: b.end))
        .toList();

    final slots = <TimeSlot>[];
    for (var minutes = hours.openMinutes;
        minutes + serviceDurationMinutes <= hours.closeMinutes;
        minutes += AppConstants.slotGridMinutes) {
      final start = dayStart.add(Duration(minutes: minutes));
      final end = start.add(Duration(minutes: serviceDurationMinutes));

      if (!start.isAfter(clock)) continue;

      final overlapsBooking = occupied
          .any((range) => start.isBefore(range.end) && end.isAfter(range.start));
      if (overlapsBooking) continue;

      final overlapsBlock = blockedSlots.any((b) => b.overlaps(start, end));
      if (overlapsBlock) continue;

      slots.add(TimeSlot(start: start, end: end));
    }
    return slots;
  }
}
