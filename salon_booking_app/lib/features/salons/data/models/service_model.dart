import 'package:cloud_firestore/cloud_firestore.dart';

import '../../domain/entities/salon_service.dart';

/// Firestore DTO for `services/{id}`.
abstract final class ServiceModel {
  static SalonService fromDoc(DocumentSnapshot<Map<String, dynamic>> doc) {
    final data = doc.data() ?? const <String, dynamic>{};
    return SalonService(
      id: doc.id,
      salonId: (data['salonId'] as String?) ?? '',
      name: (data['name'] as String?) ?? '',
      price: ((data['price'] as num?) ?? 0).toDouble(),
      durationMinutes: ((data['duration'] as num?) ?? 30).toInt(),
    );
  }

  static Map<String, dynamic> toMap(SalonService service) =>
      <String, dynamic>{
        'salonId': service.salonId,
        'name': service.name,
        'price': service.price,
        'duration': service.durationMinutes,
      };
}
