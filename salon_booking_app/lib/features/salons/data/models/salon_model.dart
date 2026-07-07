import 'package:cloud_firestore/cloud_firestore.dart';

import '../../domain/entities/salon.dart';
import '../../domain/entities/working_hours.dart';

/// Firestore DTO for `salons/{id}`.
///
/// Working hours are stored as `{ "1": {closed, open, close}, ... }` keyed by
/// DateTime.weekday, with "HH:mm"-independent integer minutes for painless
/// querying and no timezone ambiguity.
abstract final class SalonModel {
  static Salon fromDoc(DocumentSnapshot<Map<String, dynamic>> doc) {
    final data = doc.data() ?? const <String, dynamic>{};
    final geo = data['location'] as GeoPoint?;
    return Salon(
      id: doc.id,
      ownerId: (data['ownerId'] as String?) ?? '',
      name: (data['name'] as String?) ?? '',
      description: (data['description'] as String?) ?? '',
      address: (data['address'] as String?) ?? '',
      city: (data['city'] as String?) ?? '',
      latitude: geo?.latitude ?? 0,
      longitude: geo?.longitude ?? 0,
      images: ((data['images'] as List<dynamic>?) ?? const [])
          .whereType<String>()
          .toList(),
      rating: ((data['rating'] as num?) ?? 0).toDouble(),
      ratingCount: ((data['ratingCount'] as num?) ?? 0).toInt(),
      audience: SalonAudience.parse(data['type'] as String?),
      startingPrice: ((data['startingPrice'] as num?) ?? 0).toDouble(),
      workingHours: _hoursFromMap(data['workingHours']),
      createdAt:
          (data['createdAt'] as Timestamp?)?.toDate() ?? DateTime.now(),
    );
  }

  static Map<String, dynamic> toMap(Salon salon) => <String, dynamic>{
        'ownerId': salon.ownerId,
        'name': salon.name,
        'description': salon.description,
        'address': salon.address,
        'city': salon.city,
        'location': GeoPoint(salon.latitude, salon.longitude),
        'images': salon.images,
        'rating': salon.rating,
        'ratingCount': salon.ratingCount,
        'type': salon.audience.value,
        'startingPrice': salon.startingPrice,
        'workingHours': hoursToMap(salon.workingHours),
        'createdAt': Timestamp.fromDate(salon.createdAt),
      };

  static Map<String, dynamic> hoursToMap(WeeklyHours hours) =>
      <String, dynamic>{
        for (final entry in hours.days.entries)
          '${entry.key}': <String, dynamic>{
            'closed': entry.value.closed,
            'open': entry.value.openMinutes,
            'close': entry.value.closeMinutes,
          },
      };

  static WeeklyHours _hoursFromMap(Object? raw) {
    if (raw is! Map<String, dynamic>) return WeeklyHours.standard();
    final days = <int, DayHours>{};
    for (final entry in raw.entries) {
      final weekday = int.tryParse(entry.key);
      final value = entry.value;
      if (weekday == null || value is! Map<String, dynamic>) continue;
      days[weekday] = DayHours(
        closed: (value['closed'] as bool?) ?? false,
        openMinutes: ((value['open'] as num?) ?? 0).toInt(),
        closeMinutes: ((value['close'] as num?) ?? 0).toInt(),
      );
    }
    return days.isEmpty ? WeeklyHours.standard() : WeeklyHours(days);
  }
}
