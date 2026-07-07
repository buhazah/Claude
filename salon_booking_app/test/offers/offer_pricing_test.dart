import 'package:flutter_test/flutter_test.dart';
import 'package:salon_booking_app/features/offers/domain/entities/offer.dart';
import 'package:salon_booking_app/features/offers/domain/services/offer_pricing.dart';

Offer _offer({
  String id = 'o1',
  String salonId = 's1',
  int discount = 20,
  required DateTime start,
  required DateTime end,
  bool active = true,
  int maxRedemptions = 0,
  int redemptionCount = 0,
}) =>
    Offer(
      id: id,
      salonId: salonId,
      salonName: 'Salon',
      title: 'Deal',
      discountPercent: discount,
      startTime: start,
      endTime: end,
      active: active,
      maxRedemptions: maxRedemptions,
      redemptionCount: redemptionCount,
      createdAt: DateTime(2026),
    );

void main() {
  final now = DateTime(2026, 7, 8, 16); // 4pm — inside a 3–6pm window.
  final start = DateTime(2026, 7, 8, 15);
  final end = DateTime(2026, 7, 8, 18);

  test('picks the highest live discount for the salon', () {
    final best = OfferPricing.bestLiveOffer(
      [
        _offer(id: 'small', discount: 10, start: start, end: end),
        _offer(id: 'big', discount: 30, start: start, end: end),
        _offer(id: 'other-salon', salonId: 's2', discount: 50, start: start, end: end),
      ],
      's1',
      moment: now,
    );
    expect(best?.id, 'big');
  });

  test('ignores inactive, expired and sold-out offers', () {
    final best = OfferPricing.bestLiveOffer(
      [
        _offer(id: 'inactive', active: false, start: start, end: end),
        _offer(
          id: 'expired',
          start: DateTime(2026, 7, 7),
          end: DateTime(2026, 7, 7, 12),
        ),
        _offer(
          id: 'sold-out',
          start: start,
          end: end,
          maxRedemptions: 5,
          redemptionCount: 5,
        ),
      ],
      's1',
      moment: now,
    );
    expect(best, isNull);
  });

  test('applies the discount and rounds to 2 decimals', () {
    final offer = _offer(discount: 25, start: start, end: end);
    expect(OfferPricing.discountedPrice(199.99, offer), 149.99);
    expect(OfferPricing.discountedPrice(100, offer), 75.0);
  });
}
