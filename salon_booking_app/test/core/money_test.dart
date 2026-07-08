import 'package:flutter_test/flutter_test.dart';
import 'package:salon_booking_app/core/utils/money.dart';

void main() {
  test('parses AED input into fils', () {
    expect(Money.tryParseAed('120'), const Money(12000));
    expect(Money.tryParseAed('99.5'), const Money(9950));
    expect(Money.tryParseAed(' 0.01 '), const Money(1));
    expect(Money.tryParseAed('abc'), isNull);
    expect(Money.tryParseAed('-5'), isNull);
  });

  test('discounts round to the nearest fils, no floating point drift', () {
    // 33% off 99.99 AED = 66.9933 AED → 6699 fils.
    expect(const Money(9999).discountedBy(33), const Money(6699));
    expect(const Money(10000).discountedBy(0), const Money(10000));
    expect(const Money(10000).discountedBy(100), const Money(0));
    // Out-of-range percentages clamp instead of corrupting the price.
    expect(const Money(10000).discountedBy(150), const Money(0));
  });

  test('sums and compares on fils', () {
    expect(const Money(150) + const Money(50), const Money(200));
    expect(const Money(100) < const Money(101), isTrue);
    expect(const Money(0).isZero, isTrue);
    expect(const Money(12345).aed, 123.45);
  });
}
