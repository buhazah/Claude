import 'dart:math' as math;

/// Lightweight geo helpers for "nearby" sorting.
///
/// The MVP sorts client-side by haversine distance from a reference point
/// (device location later — see [AppConstants.defaultLatitude]). When salon
/// counts grow, move to geohash queries (e.g. geoflutterfire_plus) behind the
/// same SalonRepository interface — no UI change required.
abstract final class GeoUtils {
  static const double _earthRadiusKm = 6371;

  static double distanceKm(
    double lat1,
    double lon1,
    double lat2,
    double lon2,
  ) {
    final dLat = _toRad(lat2 - lat1);
    final dLon = _toRad(lon2 - lon1);
    final a = math.sin(dLat / 2) * math.sin(dLat / 2) +
        math.cos(_toRad(lat1)) *
            math.cos(_toRad(lat2)) *
            math.sin(dLon / 2) *
            math.sin(dLon / 2);
    final c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a));
    return _earthRadiusKm * c;
  }

  static String formatDistance(double km) =>
      km < 1 ? '${(km * 1000).round()} m' : '${km.toStringAsFixed(1)} km';

  static double _toRad(double deg) => deg * math.pi / 180;
}
