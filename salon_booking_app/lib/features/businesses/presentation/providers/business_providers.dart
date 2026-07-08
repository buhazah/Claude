import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/di/firebase_providers.dart';
import '../../../auth/presentation/providers/auth_providers.dart';
import '../../data/repositories/firestore_business_repository.dart';
import '../../domain/entities/blocked_slot.dart';
import '../../domain/entities/bookable_resource.dart';
import '../../domain/entities/business.dart';
import '../../domain/entities/discovery_filters.dart';
import '../../domain/entities/service_offering.dart';
import '../../domain/repositories/business_repository.dart';

final businessRepositoryProvider = Provider<BusinessRepository>(
  (ref) =>
      FirestoreBusinessRepository(firestore: ref.watch(firestoreProvider)),
);

/// Active discovery filters (mutated by the home filter sheet).
final discoveryFiltersProvider =
    NotifierProvider<DiscoveryFiltersNotifier, DiscoveryFilters>(
        DiscoveryFiltersNotifier.new);

class DiscoveryFiltersNotifier extends Notifier<DiscoveryFilters> {
  @override
  DiscoveryFilters build() => const DiscoveryFilters();

  void apply(DiscoveryFilters filters) => state = filters;

  void reset() => state = const DiscoveryFilters();
}

/// Business detail (live).
final businessProvider = StreamProvider.family<Business?, String>(
  (ref, businessId) =>
      ref.watch(businessRepositoryProvider).watchBusiness(businessId),
);

/// Services of a business (live) — detail screen and owner dashboard.
final businessServicesProvider =
    StreamProvider.family<List<ServiceOffering>, String>(
  (ref, businessId) =>
      ref.watch(businessRepositoryProvider).watchServices(businessId),
);

/// Capacity resources of a business (live).
final businessResourcesProvider =
    StreamProvider.family<List<BookableResource>, String>(
  (ref, businessId) =>
      ref.watch(businessRepositoryProvider).watchResources(businessId),
);

/// Bookable capacity: number of resources, minimum 1 (a business that has
/// not defined resources yet still takes one booking per slot).
final businessCapacityProvider = Provider.family<AsyncValue<int>, String>(
  (ref, businessId) => ref
      .watch(businessResourcesProvider(businessId))
      .whenData((resources) => resources.isEmpty ? 1 : resources.length),
);

/// Upcoming blocked slots of a business (live).
final blockedSlotsProvider = StreamProvider.family<List<BlockedSlot>, String>(
  (ref, businessId) => ref
      .watch(businessRepositoryProvider)
      .watchUpcomingBlockedSlots(businessId),
);

/// All businesses owned by the signed-in owner (multi-branch).
final ownerBusinessesProvider = StreamProvider<List<Business>>((ref) {
  final user = ref.watch(currentUserProvider).valueOrNull;
  if (user == null) return Stream.value(const []);
  return ref.watch(businessRepositoryProvider).watchOwnerBusinesses(user.id);
});

/// Which of the owner's businesses is active in the dashboard.
final selectedBusinessIdProvider =
    NotifierProvider<SelectedBusinessIdNotifier, String?>(
        SelectedBusinessIdNotifier.new);

class SelectedBusinessIdNotifier extends Notifier<String?> {
  @override
  String? build() => null;

  void select(String? businessId) => state = businessId;
}

/// The owner's active business: the selected one, else the first.
/// Null while the owner hasn't created a business yet.
final ownerBusinessProvider = Provider<AsyncValue<Business?>>((ref) {
  final businesses = ref.watch(ownerBusinessesProvider);
  final selectedId = ref.watch(selectedBusinessIdProvider);
  return businesses.whenData((list) {
    if (list.isEmpty) return null;
    for (final business in list) {
      if (business.id == selectedId) return business;
    }
    return list.first;
  });
});
