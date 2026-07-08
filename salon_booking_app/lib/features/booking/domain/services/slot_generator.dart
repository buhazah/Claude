import '../../../../core/constants/app_constants.dart';
import '../../../businesses/domain/entities/working_hours.dart';
import '../entities/time_range.dart';
import '../entities/time_slot.dart';

/// Pure business logic: computes which slots a customer can book.
///
/// Capacity-aware: a business with N interchangeable resources (chairs /
/// rooms / staff) can take N overlapping bookings. Inputs are plain domain
/// objects — no Firebase/Flutter types — and exhaustively unit-tested in
/// test/booking/slot_generator_test.dart.
abstract final class SlotGenerator {
  /// Available slots on [day] for a service lasting [serviceDurationMinutes].
  ///
  /// A slot on the [AppConstants.slotGridMinutes] grid is offered when it:
  ///  * fits fully inside the business's working hours for that weekday,
  ///  * overlaps fewer than [capacity] busy ranges (taken bookings),
  ///  * doesn't overlap an owner-blocked range (blocks ALL capacity),
  ///  * starts in the future (for today).
  static List<TimeSlot> generate({
    required DateTime day,
    required int serviceDurationMinutes,
    required WeeklyHours workingHours,
    required int capacity,
    required List<TimeRange> busyRanges,
    required List<TimeRange> blockedRanges,
    DateTime? now,
  }) {
    assert(capacity >= 1, 'capacity must be at least 1');
    final hours = workingHours.forWeekday(day.weekday);
    if (hours.closed || hours.closeMinutes <= hours.openMinutes) {
      return const [];
    }

    final clock = now ?? DateTime.now();
    final dayStart = DateTime(day.year, day.month, day.day);

    final slots = <TimeSlot>[];
    for (var minutes = hours.openMinutes;
        minutes + serviceDurationMinutes <= hours.closeMinutes;
        minutes += AppConstants.slotGridMinutes) {
      final start = dayStart.add(Duration(minutes: minutes));
      final end = start.add(Duration(minutes: serviceDurationMinutes));

      if (!start.isAfter(clock)) continue;

      final blocked = blockedRanges.any((b) => b.overlaps(start, end));
      if (blocked) continue;

      final overlappingBusy =
          busyRanges.where((b) => b.overlaps(start, end)).length;
      if (overlappingBusy >= capacity) continue;

      slots.add(TimeSlot(start: start, end: end));
    }
    return slots;
  }
}
