import '../../../../core/utils/money.dart';

/// A bookable service offered by a business (haircut, massage, checkup…).
class ServiceOffering {
  const ServiceOffering({
    required this.id,
    required this.businessId,
    required this.name,
    required this.price,
    required this.durationMinutes,
  });

  final String id;
  final String businessId;
  final String name;

  /// Base price. Offer discounts are applied at booking time
  /// (see OfferPricing) — never mutated here.
  final Money price;
  final int durationMinutes;

  ServiceOffering copyWith({String? name, Money? price, int? durationMinutes}) =>
      ServiceOffering(
        id: id,
        businessId: businessId,
        name: name ?? this.name,
        price: price ?? this.price,
        durationMinutes: durationMinutes ?? this.durationMinutes,
      );
}
