import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/di/firebase_providers.dart';
import '../../../auth/presentation/providers/auth_providers.dart';
import '../../data/repositories/firestore_salon_repository.dart';
import '../../domain/entities/blocked_slot.dart';
import '../../domain/entities/salon.dart';
import '../../domain/entities/salon_filters.dart';
import '../../domain/entities/salon_service.dart';
import '../../domain/repositories/salon_repository.dart';

final salonRepositoryProvider = Provider<SalonRepository>(
  (ref) => FirestoreSalonRepository(firestore: ref.watch(firestoreProvider)),
);

/// Active discovery filters (mutated by the home filter sheet).
final salonFiltersProvider =
    NotifierProvider<SalonFiltersNotifier, SalonFilters>(
        SalonFiltersNotifier.new);

class SalonFiltersNotifier extends Notifier<SalonFilters> {
  @override
  SalonFilters build() => const SalonFilters();

  void apply(SalonFilters filters) => state = filters;

  void reset() => state = const SalonFilters();
}

/// Salon detail (live).
final salonProvider = StreamProvider.family<Salon?, String>(
  (ref, salonId) => ref.watch(salonRepositoryProvider).watchSalon(salonId),
);

/// Services of a salon (live) — used by detail screen and owner dashboard.
final salonServicesProvider = StreamProvider.family<List<SalonService>, String>(
  (ref, salonId) => ref.watch(salonRepositoryProvider).watchServices(salonId),
);

/// Blocked slots of a salon (live).
final blockedSlotsProvider = StreamProvider.family<List<BlockedSlot>, String>(
  (ref, salonId) =>
      ref.watch(salonRepositoryProvider).watchBlockedSlots(salonId),
);

/// The signed-in owner's salon; null while it hasn't been created yet.
final ownerSalonProvider = StreamProvider<Salon?>((ref) {
  final user = ref.watch(currentUserProvider).valueOrNull;
  if (user == null) return Stream.value(null);
  return ref.watch(salonRepositoryProvider).watchOwnerSalon(user.id);
});
