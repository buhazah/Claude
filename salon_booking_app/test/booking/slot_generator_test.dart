import 'package:flutter_test/flutter_test.dart';
import 'package:salon_booking_app/features/booking/domain/entities/time_range.dart';
import 'package:salon_booking_app/features/booking/domain/services/slot_generator.dart';
import 'package:salon_booking_app/features/businesses/domain/entities/working_hours.dart';

TimeRange _range(DateTime start, int minutes) =>
    TimeRange(start: start, end: start.add(Duration(minutes: minutes)));

void main() {
  // A Wednesday. Business open 10:00–13:00 for compact expectations.
  final day = DateTime(2026, 7, 8);
  final hours = WeeklyHours({
    DateTime.wednesday:
        const DayHours(closed: false, openMinutes: 600, closeMinutes: 780),
  });
  final earlyMorning = DateTime(2026, 7, 8, 6);

  test('generates slots on the 30-minute grid within working hours', () {
    final slots = SlotGenerator.generate(
      day: day,
      serviceDurationMinutes: 60,
      workingHours: hours,
      capacity: 1,
      busyRanges: const [],
      blockedRanges: const [],
      now: earlyMorning,
    );
    // 10:00, 10:30, 11:00, 11:30, 12:00 (12:30 + 60min exceeds 13:00).
    expect(slots.length, 5);
    expect(slots.first.start, DateTime(2026, 7, 8, 10));
    expect(slots.last.start, DateTime(2026, 7, 8, 12));
  });

  test('capacity 1: excludes slots overlapping a busy range', () {
    final slots = SlotGenerator.generate(
      day: day,
      serviceDurationMinutes: 60,
      workingHours: hours,
      capacity: 1,
      busyRanges: [_range(DateTime(2026, 7, 8, 10, 30), 60)],
      blockedRanges: const [],
      now: earlyMorning,
    );
    // 10:00/10:30/11:00 starts collide with the 10:30–11:30 busy range.
    expect(
      slots.map((s) => s.start.hour * 100 + s.start.minute).toList(),
      [1130, 1200],
    );
  });

  test('capacity 2: one overlapping booking leaves the slot available', () {
    final slots = SlotGenerator.generate(
      day: day,
      serviceDurationMinutes: 60,
      workingHours: hours,
      capacity: 2,
      busyRanges: [_range(DateTime(2026, 7, 8, 10, 30), 60)],
      blockedRanges: const [],
      now: earlyMorning,
    );
    // Second chair free → all 5 grid slots offered.
    expect(slots.length, 5);
  });

  test('capacity 2: two overlapping bookings fill the slot', () {
    final slots = SlotGenerator.generate(
      day: day,
      serviceDurationMinutes: 60,
      workingHours: hours,
      capacity: 2,
      busyRanges: [
        _range(DateTime(2026, 7, 8, 10, 30), 60),
        _range(DateTime(2026, 7, 8, 10, 30), 60),
      ],
      blockedRanges: const [],
      now: earlyMorning,
    );
    expect(
      slots.map((s) => s.start.hour * 100 + s.start.minute).toList(),
      [1130, 1200],
    );
  });

  test('blocked ranges block all capacity', () {
    final slots = SlotGenerator.generate(
      day: day,
      serviceDurationMinutes: 30,
      workingHours: hours,
      capacity: 5,
      busyRanges: const [],
      blockedRanges: [
        TimeRange(
          start: DateTime(2026, 7, 8, 11),
          end: DateTime(2026, 7, 8, 12),
        ),
      ],
      now: earlyMorning,
    );
    expect(
      slots.any((s) =>
          s.start.isBefore(DateTime(2026, 7, 8, 12)) &&
          s.end.isAfter(DateTime(2026, 7, 8, 11))),
      isFalse,
    );
  });

  test('excludes past slots for today', () {
    final slots = SlotGenerator.generate(
      day: day,
      serviceDurationMinutes: 30,
      workingHours: hours,
      capacity: 1,
      busyRanges: const [],
      blockedRanges: const [],
      now: DateTime(2026, 7, 8, 11, 45),
    );
    expect(slots.first.start, DateTime(2026, 7, 8, 12));
  });

  test('returns nothing on closed days', () {
    final slots = SlotGenerator.generate(
      day: DateTime(2026, 7, 9), // Thursday — not in the schedule map.
      serviceDurationMinutes: 30,
      workingHours: hours,
      capacity: 1,
      busyRanges: const [],
      blockedRanges: const [],
      now: earlyMorning,
    );
    expect(slots, isEmpty);
  });
}
