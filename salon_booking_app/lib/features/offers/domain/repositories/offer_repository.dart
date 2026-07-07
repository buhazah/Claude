import '../entities/offer.dart';

/// Contract for offer discovery + owner-side offer management.
abstract interface class OfferRepository {
  /// Offers that could currently be live (active flag + not yet ended).
  /// Final `isLiveAt` filtering happens in the domain layer.
  Stream<List<Offer>> watchLiveOffers();

  /// All offers of one salon (owner management list).
  Stream<List<Offer>> watchSalonOffers(String salonId);

  Future<void> createOffer(Offer offer);
  Future<void> setActive(String offerId, bool active);
  Future<void> deleteOffer(String offerId);

  /// Atomically counts a redemption when a discounted booking is created.
  Future<void> incrementRedemption(String offerId);
}
