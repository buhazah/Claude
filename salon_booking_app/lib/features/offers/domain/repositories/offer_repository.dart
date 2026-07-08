import '../entities/offer.dart';

/// Contract for offer discovery + owner-side offer management.
///
/// Redemption counting is deliberately absent: it happens atomically inside
/// BookingRepository.createBooking, in the same write batch as the booking.
abstract interface class OfferRepository {
  /// Offers that could currently be live (active flag + not yet ended).
  /// Final `isLiveAt` filtering happens in the domain layer.
  Stream<List<Offer>> watchLiveOffers();

  /// All offers of one business (owner management list + detail banner).
  Stream<List<Offer>> watchBusinessOffers(String businessId);

  Future<void> createOffer(Offer offer);
  Future<void> setActive(String offerId, bool active);
  Future<void> deleteOffer(String offerId);
}
