import 'package:cloud_firestore/cloud_firestore.dart';

import '../../../../core/utils/money.dart';
import '../../domain/entities/business.dart';
import '../../domain/entities/working_hours.dart';

/// Firestore DTO for `businesses/{id}`.
///
/// Working hours are stored as `{ "1": {closed, open, close}, ... }` keyed
/// by DateTime.weekday, with integer minutes (no timezone ambiguity).
abstract final class BusinessModel {
  static Business fromDoc(DocumentSnapshot<Map<String, dynamic>> doc) {
    final data = doc.data() ?? const <String, dynamic>{};
    final geo = data['location'] as GeoPoint?;
    return Business(
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
      audience: Audience.parse(data['audience'] as String?),
      category: BusinessCategory.parse(data['category'] as String?),
      approved: (data['approved'] as bool?) ?? false,
      startingPrice:
          Money(((data['startingPriceFils'] as num?) ?? 0).toInt()),
      workingHours: _hoursFromMap(data['workingHours']),
      createdAt:
          (data['createdAt'] as Timestamp?)?.toDate() ?? DateTime.now(),
    );
  }

  static Map<String, dynamic> toMap(Business business) => <String, dynamic>{
        'ownerId': business.ownerId,
        'name': business.name,
        'description': business.description,
        'address': business.address,
        'city': business.city,
        'location': GeoPoint(business.latitude, business.longitude),
        'images': business.images,
        'rating': business.rating,
        'ratingCount': business.ratingCount,
        'audience': business.audience.value,
        'category': business.category.value,
        'approved': business.approved,
        'startingPriceFils': business.startingPrice.fils,
        'workingHours': hoursToMap(business.workingHours),
        'createdAt': Timestamp.fromDate(business.createdAt),
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
