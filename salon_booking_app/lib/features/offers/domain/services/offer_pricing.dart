import '../entities/offer.dart';

/// Pure pricing logic — how offers translate into the price a customer pays.
/// Kept out of UI and repositories so it is trivially unit-testable and can
/// move server-side (Cloud Function) untouched when payments arrive.
abstract final class OfferPricing {
  /// The best live offer for a salon at [moment], or null.
  /// "Best" = largest discount; ties broken by earliest end (urgency).
  static Offer? bestLiveOffer(
    List<Offer> offers,
    String salonId, {
    DateTime? moment,
  }) {
    final at = moment ?? DateTime.now();
    final candidates = offers
        .where((o) => o.salonId == salonId && o.isLiveAt(at))
        .toList()
      ..sort((a, b) {
        final byDiscount = b.discountPercent.compareTo(a.discountPercent);
        return byDiscount != 0 ? byDiscount : a.endTime.compareTo(b.endTime);
      });
    return candidates.isEmpty ? null : candidates.first;
  }

  /// Price after applying [offer] (rounded to fils / 2 decimals).
  static double discountedPrice(double basePrice, Offer offer) {
    final factor = (100 - offer.discountPercent.clamp(0, 100)) / 100;
    return double.parse((basePrice * factor).toStringAsFixed(2));
  }
}
