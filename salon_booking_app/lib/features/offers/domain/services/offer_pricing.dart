import '../../../../core/utils/money.dart';
import '../entities/offer.dart';

/// Pure pricing logic — how offers translate into the price a customer pays.
/// Kept out of UI and repositories so it is trivially unit-testable and can
/// move server-side (Cloud Function) untouched when payments arrive.
abstract final class OfferPricing {
  /// The best live offer for a business at [moment], or null.
  /// "Best" = largest discount; ties broken by earliest end (urgency).
  static Offer? bestLiveOffer(
    List<Offer> offers,
    String businessId, {
    DateTime? moment,
  }) {
    final at = moment ?? DateTime.now();
    final candidates = offers
        .where((o) => o.businessId == businessId && o.isLiveAt(at))
        .toList()
      ..sort((a, b) {
        final byDiscount = b.discountPercent.compareTo(a.discountPercent);
        return byDiscount != 0 ? byDiscount : a.endTime.compareTo(b.endTime);
      });
    return candidates.isEmpty ? null : candidates.first;
  }

  /// Price after applying [offer], on integer fils (no floating point).
  static Money discountedPrice(Money basePrice, Offer offer) =>
      basePrice.discountedBy(offer.discountPercent);
}
