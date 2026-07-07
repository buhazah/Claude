import 'working_hours.dart';

/// Which clientele the salon serves — used by the gender filter.
enum SalonAudience {
  male('male'),
  female('female'),
  both('both');

  const SalonAudience(this.value);
  final String value;

  static SalonAudience parse(String? raw) =>
      SalonAudience.values.firstWhere(
        (a) => a.value == raw,
        orElse: () => SalonAudience.both,
      );

  String get label => switch (this) {
        SalonAudience.male => 'Men',
        SalonAudience.female => 'Women',
        SalonAudience.both => 'Unisex',
      };
}

/// Domain salon — pure Dart, no Firebase types.
class Salon {
  const Salon({
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
  final SalonAudience audience;

  /// Denormalized min service price (AED) for cheap list-screen filtering.
  /// Recomputed on service writes (see FirestoreSalonRepository).
  final double startingPrice;
  final WeeklyHours workingHours;
  final DateTime createdAt;

  String? get coverImage => images.isEmpty ? null : images.first;
}
