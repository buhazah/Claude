import 'package:flutter_test/flutter_test.dart';
import 'package:salon_booking_app/core/utils/money.dart';
import 'package:salon_booking_app/features/offers/domain/entities/offer.dart';
import 'package:salon_booking_app/features/offers/domain/services/offer_pricing.dart';

Offer _offer({
  String id = 'o1',
  String businessId = 'b1',
  int discount = 20,
  required DateTime start,
  required DateTime end,
  bool active = true,
  int maxRedemptions = 0,
  int redemptionCount = 0,
  int? dailyStartMinute,
  int? dailyEndMinute,
}) =>
    Offer(
      id: id,
      businessId: businessId,
      businessName: 'Glow Lounge',
      title: 'Deal',
      discountPercent: discount,
      startTime: start,
      endTime: end,
      active: active,
      maxRedemptions: maxRedemptions,
      redemptionCount: redemptionCount,
      createdAt: DateTime(2026),
      dailyStartMinute: dailyStartMinute,
      dailyEndMinute: dailyEndMinute,
    );

void main() {
  final now = DateTime(2026, 7, 8, 16); // 4pm.
  final start = DateTime(2026, 7, 8);
  final end = DateTime(2026, 7, 15);

  test('picks the highest live discount for the business', () {
    final best = OfferPricing.bestLiveOffer(
      [
        _offer(id: 'small', discount: 10, start: start, end: end),
        _offer(id: 'big', discount: 30, start: start, end: end),
        _offer(
            id: 'other-business',
            businessId: 'b2',
            discount: 50,
            start: start,
            end: end),
      ],
      'b1',
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
          start: DateTime(2026, 7, 1),
          end: DateTime(2026, 7, 7),
        ),
        _offer(
          id: 'sold-out',
          start: start,
          end: end,
          maxRedemptions: 5,
          redemptionCount: 5,
        ),
      ],
      'b1',
      moment: now,
    );
    expect(best, isNull);
  });

  test('daily window: live inside the window, dead outside it', () {
    final happyHour = _offer(
      start: start,
      end: end,
      dailyStartMinute: 15 * 60, // 3pm
      dailyEndMinute: 18 * 60, // 6pm
    );
    expect(happyHour.isLiveAt(DateTime(2026, 7, 8, 16)), isTrue); // 4pm
    expect(happyHour.isLiveAt(DateTime(2026, 7, 8, 14)), isFalse); // 2pm
    expect(happyHour.isLiveAt(DateTime(2026, 7, 8, 18)), isFalse); // 6pm sharp
    // Recurs the next day too.
    expect(happyHour.isLiveAt(DateTime(2026, 7, 9, 16)), isTrue);
  });

  test('applies the discount on integer fils', () {
    final offer = _offer(discount: 25, start: start, end: end);
    expect(
      OfferPricing.discountedPrice(const Money(19999), offer),
      const Money(14999),
    );
    expect(
      OfferPricing.discountedPrice(const Money(10000), offer),
      const Money(7500),
    );
  });
}
