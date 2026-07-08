import 'package:cloud_firestore/cloud_firestore.dart';

import '../../../../core/utils/money.dart';
import '../../domain/entities/service_offering.dart';

/// Firestore DTO for `services/{id}`.
abstract final class ServiceOfferingModel {
  static ServiceOffering fromDoc(DocumentSnapshot<Map<String, dynamic>> doc) {
    final data = doc.data() ?? const <String, dynamic>{};
    return ServiceOffering(
      id: doc.id,
      businessId: (data['businessId'] as String?) ?? '',
      name: (data['name'] as String?) ?? '',
      price: Money(((data['priceFils'] as num?) ?? 0).toInt()),
      durationMinutes: ((data['durationMinutes'] as num?) ?? 30).toInt(),
    );
  }

  static Map<String, dynamic> toMap(ServiceOffering service) =>
      <String, dynamic>{
        'businessId': service.businessId,
        'name': service.name,
        'priceFils': service.price.fils,
        'durationMinutes': service.durationMinutes,
      };
}
