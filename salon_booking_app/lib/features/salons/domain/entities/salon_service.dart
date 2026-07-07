/// A bookable service offered by a salon (haircut, manicure, …).
class SalonService {
  const SalonService({
    required this.id,
    required this.salonId,
    required this.name,
    required this.price,
    required this.durationMinutes,
  });

  final String id;
  final String salonId;
  final String name;

  /// Base price in AED. Offer discounts are applied at booking time
  /// (see OfferPricing) — never mutated here.
  final double price;
  final int durationMinutes;

  SalonService copyWith({String? name, double? price, int? durationMinutes}) =>
      SalonService(
        id: id,
        salonId: salonId,
        name: name ?? this.name,
        price: price ?? this.price,
        durationMinutes: durationMinutes ?? this.durationMinutes,
      );
}
