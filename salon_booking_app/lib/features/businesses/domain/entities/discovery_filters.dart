import '../../../../core/constants/app_constants.dart';
import 'business.dart';

/// Immutable discovery filters (category / gender / price / rating).
///
/// Audience and category are pushed into the Firestore query; price and
/// rating are applied in-memory on the fetched page — fine at MVP scale,
/// and the split is documented on BusinessRepository.watchBusinesses for
/// when it needs to move server-side.
class DiscoveryFilters {
  const DiscoveryFilters({
    this.audience,
    this.category,
    this.minRating = 0,
    this.minPriceAed = AppConstants.minFilterPrice,
    this.maxPriceAed = AppConstants.maxFilterPrice,
  });

  /// null = any.
  final Audience? audience;
  final BusinessCategory? category;
  final double minRating;

  /// AED bounds straight from the range slider (UI-space; compared against
  /// Money via .aed).
  final double minPriceAed;
  final double maxPriceAed;

  bool get isDefault =>
      audience == null &&
      category == null &&
      minRating == 0 &&
      minPriceAed == AppConstants.minFilterPrice &&
      maxPriceAed == AppConstants.maxFilterPrice;

  bool matches(Business business) {
    if (business.rating < minRating) return false;
    // Businesses without services yet (startingPrice == 0) always pass the
    // price filter rather than vanishing from discovery.
    final startingAed = business.startingPrice.aed;
    if (!business.startingPrice.isZero &&
        (startingAed < minPriceAed || startingAed > maxPriceAed)) {
      return false;
    }
    return true;
  }

  DiscoveryFilters copyWith({
    Audience? Function()? audience,
    BusinessCategory? Function()? category,
    double? minRating,
    double? minPriceAed,
    double? maxPriceAed,
  }) =>
      DiscoveryFilters(
        audience: audience == null ? this.audience : audience(),
        category: category == null ? this.category : category(),
        minRating: minRating ?? this.minRating,
        minPriceAed: minPriceAed ?? this.minPriceAed,
        maxPriceAed: maxPriceAed ?? this.maxPriceAed,
      );
}
