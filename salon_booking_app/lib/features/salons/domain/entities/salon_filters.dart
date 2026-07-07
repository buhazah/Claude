import '../../../../core/constants/app_constants.dart';
import 'salon.dart';

/// Immutable discovery filters (gender / price / rating).
///
/// Audience filtering happens in the Firestore query; price and rating are
/// applied in-memory on the fetched page — fine at MVP scale, and the split
/// is documented on SalonRepository.watchSalons for when it needs to move
/// server-side.
class SalonFilters {
  const SalonFilters({
    this.audience,
    this.minRating = 0,
    this.minPrice = AppConstants.minFilterPrice,
    this.maxPrice = AppConstants.maxFilterPrice,
  });

  /// null = any audience.
  final SalonAudience? audience;
  final double minRating;
  final double minPrice;
  final double maxPrice;

  bool get isDefault =>
      audience == null &&
      minRating == 0 &&
      minPrice == AppConstants.minFilterPrice &&
      maxPrice == AppConstants.maxFilterPrice;

  bool matches(Salon salon) {
    if (salon.rating < minRating) return false;
    // Salons without services yet (startingPrice == 0) always pass the
    // price filter rather than vanishing from discovery.
    if (salon.startingPrice > 0 &&
        (salon.startingPrice < minPrice || salon.startingPrice > maxPrice)) {
      return false;
    }
    return true;
  }

  SalonFilters copyWith({
    SalonAudience? Function()? audience,
    double? minRating,
    double? minPrice,
    double? maxPrice,
  }) =>
      SalonFilters(
        audience: audience == null ? this.audience : audience(),
        minRating: minRating ?? this.minRating,
        minPrice: minPrice ?? this.minPrice,
        maxPrice: maxPrice ?? this.maxPrice,
      );
}
