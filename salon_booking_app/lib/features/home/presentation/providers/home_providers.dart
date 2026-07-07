import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/constants/app_constants.dart';
import '../../../../core/utils/geo_utils.dart';
import '../../../salons/domain/entities/salon.dart';
import '../../../salons/presentation/providers/salon_providers.dart';

/// A salon plus its distance from the reference point, for "nearby" UI.
typedef NearbySalon = ({Salon salon, double distanceKm});

/// Reference location for distance sorting. MVP: fixed city center.
/// Swap the implementation for a geolocator-backed provider without touching
/// any consumer (they only see (lat, lng)).
final referenceLocationProvider = Provider<({double lat, double lng})>(
  (ref) => (
    lat: AppConstants.defaultLatitude,
    lng: AppConstants.defaultLongitude,
  ),
);

/// Discovery list: filtered salons sorted nearest-first.
final nearbySalonsProvider = StreamProvider<List<NearbySalon>>((ref) {
  final filters = ref.watch(salonFiltersProvider);
  final origin = ref.watch(referenceLocationProvider);

  return ref.watch(salonRepositoryProvider).watchSalons(filters).map((salons) {
    final withDistance = salons
        .map<NearbySalon>((salon) => (
              salon: salon,
              distanceKm: GeoUtils.distanceKm(
                origin.lat,
                origin.lng,
                salon.latitude,
                salon.longitude,
              ),
            ))
        .toList()
      ..sort((a, b) => a.distanceKm.compareTo(b.distanceKm));
    return withDistance;
  });
});
