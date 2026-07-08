import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/di/firebase_providers.dart';
import '../../../auth/presentation/providers/auth_providers.dart';
import '../../../businesses/presentation/providers/business_providers.dart';
import '../../data/repositories/firestore_booking_repository.dart';
import '../../domain/entities/booking.dart';
import '../../domain/entities/busy_slot.dart';
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

/// Public busy slots of a business for one calendar day.
final busySlotsProvider = StreamProvider.family<List<BusySlot>,
    ({String businessId, DateTime day})>((ref, args) {
  return ref
      .watch(bookingRepositoryProvider)
      .watchBusySlots(args.businessId, args.day);
});

/// Available slots for booking a service of [durationMinutes] at a business
/// on [day]. Combines working hours + capacity + busy slots + blocked slots
/// and runs the pure [SlotGenerator]. Live: reacts to new bookings instantly.
final availableSlotsProvider = Provider.family<AsyncValue<List<TimeSlot>>,
    ({String businessId, int durationMinutes, DateTime day})>((ref, args) {
  final business = ref.watch(businessProvider(args.businessId));
  final capacity = ref.watch(businessCapacityProvider(args.businessId));
  final busy = ref.watch(
      busySlotsProvider((businessId: args.businessId, day: args.day)));
  final blocked = ref.watch(blockedSlotsProvider(args.businessId));

  if (business.isLoading ||
      capacity.isLoading ||
      busy.isLoading ||
      blocked.isLoading) {
    return const AsyncValue.loading();
  }
  final error =
      business.error ?? capacity.error ?? busy.error ?? blocked.error;
  if (error != null) {
    return AsyncValue.error(error, StackTrace.current);
  }
  final businessValue = business.valueOrNull;
  if (businessValue == null) return const AsyncValue.data([]);

  return AsyncValue.data(
    SlotGenerator.generate(
      day: args.day,
      serviceDurationMinutes: args.durationMinutes,
      workingHours: businessValue.workingHours,
      capacity: capacity.valueOrNull ?? 1,
      busyRanges: (busy.valueOrNull ?? const <BusySlot>[])
          .map((slot) => slot.range)
          .toList(),
      blockedRanges: (blocked.valueOrNull ?? const [])
          .map((slot) => slot.range)
          .toList(),
    ),
  );
});
