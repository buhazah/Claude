import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/di/firebase_providers.dart';
import '../../../auth/presentation/providers/auth_providers.dart';
import '../../../salons/presentation/providers/salon_providers.dart';
import '../../data/repositories/firestore_booking_repository.dart';
import '../../domain/entities/booking.dart';
import '../../domain/entities/time_slot.dart';
import '../../domain/repositories/booking_repository.dart';
import '../../domain/services/slot_generator.dart';

final bookingRepositoryProvider = Provider<BookingRepository>(
  (ref) =>
      FirestoreBookingRepository(firestore: ref.watch(firestoreProvider)),
);

/// Signed-in customer's bookings (history + upcoming).
final myBookingsProvider = StreamProvider<List<Booking>>((ref) {
  final user = ref.watch(currentUserProvider).valueOrNull;
  if (user == null) return Stream.value(const []);
  return ref.watch(bookingRepositoryProvider).watchUserBookings(user.id);
});

/// A salon's bookings for one calendar day (owner schedule + availability).
final salonDayBookingsProvider = StreamProvider.family<List<Booking>,
    ({String salonId, DateTime day})>((ref, args) {
  return ref
      .watch(bookingRepositoryProvider)
      .watchSalonBookingsForDay(args.salonId, args.day);
});

/// A salon's bookings in a given status (owner inbox tabs).
final salonStatusBookingsProvider = StreamProvider.family<List<Booking>,
    ({String salonId, BookingStatus status})>((ref, args) {
  return ref
      .watch(bookingRepositoryProvider)
      .watchSalonBookingsByStatus(args.salonId, args.status);
});

/// Available slots for booking a service of [durationMinutes] at a salon
/// on [day]. Combines salon hours + existing bookings + blocked slots and
/// runs the pure [SlotGenerator]. Live: reacts to new bookings instantly.
final availableSlotsProvider = Provider.family<AsyncValue<List<TimeSlot>>,
    ({String salonId, int durationMinutes, DateTime day})>((ref, args) {
  final salon = ref.watch(salonProvider(args.salonId));
  final bookings = ref
      .watch(salonDayBookingsProvider((salonId: args.salonId, day: args.day)));
  final blocked = ref.watch(blockedSlotsProvider(args.salonId));

  if (salon.isLoading || bookings.isLoading || blocked.isLoading) {
    return const AsyncValue.loading();
  }
  final error = salon.error ?? bookings.error ?? blocked.error;
  if (error != null) {
    return AsyncValue.error(error, StackTrace.current);
  }
  final salonValue = salon.valueOrNull;
  if (salonValue == null) return const AsyncValue.data([]);

  return AsyncValue.data(
    SlotGenerator.generate(
      day: args.day,
      serviceDurationMinutes: args.durationMinutes,
      workingHours: salonValue.workingHours,
      existingBookings: bookings.valueOrNull ?? const [],
      blockedSlots: blocked.valueOrNull ?? const [],
    ),
  );
});
