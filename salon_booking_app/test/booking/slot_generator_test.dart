import 'package:flutter_test/flutter_test.dart';
import 'package:salon_booking_app/features/booking/domain/entities/booking.dart';
import 'package:salon_booking_app/features/booking/domain/services/slot_generator.dart';
import 'package:salon_booking_app/features/salons/domain/entities/blocked_slot.dart';
import 'package:salon_booking_app/features/salons/domain/entities/working_hours.dart';

Booking _booking(DateTime start, int minutes, BookingStatus status) =>
    Booking(
      id: 'b1',
      userId: 'u1',
      customerName: 'Test',
      salonId: 's1',
      salonName: 'Salon',
      serviceId: 'svc1',
      serviceName: 'Cut',
      price: 100,
      originalPrice: 100,
      durationMinutes: minutes,
      start: start,
      status: status,
      createdAt: DateTime(2026),
    );

void main() {
  // A Wednesday. Salon open 10:00–13:00 for compact expectations.
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
      existingBookings: const [],
      blockedSlots: const [],
      now: earlyMorning,
    );
    // 10:00, 10:30, 11:00, 11:30, 12:00 (12:30 + 60min exceeds 13:00).
    expect(slots.length, 5);
    expect(slots.first.start, DateTime(2026, 7, 8, 10));
    expect(slots.last.start, DateTime(2026, 7, 8, 12));
  });

  test('excludes slots overlapping pending/confirmed bookings only', () {
    final slots = SlotGenerator.generate(
      day: day,
      serviceDurationMinutes: 60,
      workingHours: hours,
      existingBookings: [
        _booking(DateTime(2026, 7, 8, 10, 30), 60, BookingStatus.confirmed),
        // Cancelled bookings free up their slot.
        _booking(DateTime(2026, 7, 8, 12), 60, BookingStatus.cancelled),
      ],
      blockedSlots: const [],
      now: earlyMorning,
    );
    // 10:00–11:00 and 10:30/11:00 starts collide with the confirmed booking.
    expect(
      slots.map((s) => s.start.hour * 100 + s.start.minute).toList(),
      [1130, 1200],
    );
  });

  test('excludes owner-blocked ranges', () {
    final slots = SlotGenerator.generate(
      day: day,
      serviceDurationMinutes: 30,
      workingHours: hours,
      existingBookings: const [],
      blockedSlots: [
        BlockedSlot(
          id: 'x',
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
      existingBookings: const [],
      blockedSlots: const [],
      now: DateTime(2026, 7, 8, 11, 45),
    );
    expect(slots.first.start, DateTime(2026, 7, 8, 12));
  });

  test('returns nothing on closed days', () {
    final slots = SlotGenerator.generate(
      day: DateTime(2026, 7, 9), // Thursday — not in the schedule map.
      serviceDurationMinutes: 30,
      workingHours: hours,
      existingBookings: const [],
      blockedSlots: const [],
      now: earlyMorning,
    );
    expect(slots, isEmpty);
  });
}
