import '../../../../core/utils/money.dart';
import 'working_hours.dart';

/// Which clientele the business serves — used by the gender filter.
enum Audience {
  male('male'),
  female('female'),
  both('both');

  const Audience(this.value);
  final String value;

  static Audience parse(String? raw) => Audience.values.firstWhere(
        (a) => a.value == raw,
        orElse: () => Audience.both,
      );

  String get label => switch (this) {
        Audience.male => 'Men',
        Audience.female => 'Women',
        Audience.both => 'Unisex',
      };
}

/// Marketplace vertical. Salons are the launch category; new
/// appointment-based verticals are added here — never as new collections.
enum BusinessCategory {
  salon('salon'),
  spa('spa'),
  barbershop('barbershop'),
  clinic('clinic'),
  fitness('fitness'),
  other('other');

  const BusinessCategory(this.value);
  final String value;

  static BusinessCategory parse(String? raw) =>
      BusinessCategory.values.firstWhere(
        (c) => c.value == raw,
        orElse: () => BusinessCategory.salon,
      );

  String get label => switch (this) {
        BusinessCategory.salon => 'Salon',
        BusinessCategory.spa => 'Spa',
        BusinessCategory.barbershop => 'Barbershop',
        BusinessCategory.clinic => 'Clinic',
        BusinessCategory.fitness => 'Fitness',
        BusinessCategory.other => 'Other',
      };
}

/// A bookable business on the marketplace — pure Dart, no Firebase types.
class Business {
  const Business({
    required this.id,
    required this.ownerId,
    required this.name,
    required this.description,
    required this.address,
    required this.city,
    required this.latitude,
    required this.longitude,
    required this.images,
    required this.rating,
    required this.ratingCount,
    required this.audience,
    required this.category,
    required this.approved,
    required this.startingPrice,
    required this.workingHours,
    required this.createdAt,
  });

  final String id;
  final String ownerId;
  final String name;
  final String description;
  final String address;
  final String city;
  final double latitude;
  final double longitude;
  final List<String> images;
  final double rating;
  final int ratingCount;
  final Audience audience;
  final BusinessCategory category;

  /// Marketplace listing gate: set to true by an admin (Firebase console /
  /// future admin tool). Unapproved businesses are visible only to their
  /// owner — this is what stops a self-declared "owner" from publishing.
  final bool approved;

  /// Denormalized min service price for cheap list-screen filtering.
  /// Recomputed on service writes (client-side today, Cloud Function ready).
  final Money startingPrice;
  final WeeklyHours workingHours;
  final DateTime createdAt;

  String? get coverImage => images.isEmpty ? null : images.first;
}
