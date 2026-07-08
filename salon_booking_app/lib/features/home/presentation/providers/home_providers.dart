import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/constants/app_constants.dart';
import '../../../../core/utils/geo_utils.dart';
import '../../../businesses/domain/entities/business.dart';
import '../../../businesses/presentation/providers/business_providers.dart';

/// A business plus its distance from the reference point, for "nearby" UI.
typedef NearbyBusiness = ({Business business, double distanceKm});

/// Reference location for distance sorting. MVP: fixed city center.
/// Swap the implementation for a geolocator-backed provider without touching
/// any consumer (they only see (lat, lng)).
final referenceLocationProvider = Provider<({double lat, double lng})>(
  (ref) => (
    lat: AppConstants.defaultLatitude,
    lng: AppConstants.defaultLongitude,
  ),
);

/// How many businesses discovery currently shows. Bumped by the home
/// screen's scroll listener — stream-friendly "load more" (the query limit
/// grows; Firestore reuses the open listener).
final discoveryLimitProvider =
    NotifierProvider<DiscoveryLimitNotifier, int>(DiscoveryLimitNotifier.new);

class DiscoveryLimitNotifier extends Notifier<int> {
  static const int pageSize = 20;

  @override
  int build() => pageSize;

  void loadMore() => state = state + pageSize;

  void reset() => state = pageSize;
}

/// Discovery list: filtered businesses sorted nearest-first.
final nearbyBusinessesProvider = StreamProvider<List<NearbyBusiness>>((ref) {
  final filters = ref.watch(discoveryFiltersProvider);
  final limit = ref.watch(discoveryLimitProvider);
  final origin = ref.watch(referenceLocationProvider);

  return ref
      .watch(businessRepositoryProvider)
      .watchBusinesses(filters, limit: limit)
      .map((businesses) {
    final withDistance = businesses
        .map<NearbyBusiness>((business) => (
              business: business,
              distanceKm: GeoUtils.distanceKm(
                origin.lat,
                origin.lng,
                business.latitude,
                business.longitude,
              ),
            ))
        .toList()
      ..sort((a, b) => a.distanceKm.compareTo(b.distanceKm));
    return withDistance;
  });
});
