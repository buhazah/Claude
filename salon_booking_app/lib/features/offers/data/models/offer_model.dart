import 'package:cloud_firestore/cloud_firestore.dart';

import '../../domain/entities/offer.dart';

/// Firestore DTO for `offers/{id}`.
abstract final class OfferModel {
  static Offer fromDoc(DocumentSnapshot<Map<String, dynamic>> doc) {
    final data = doc.data() ?? const <String, dynamic>{};
    return Offer(
      id: doc.id,
      businessId: (data['businessId'] as String?) ?? '',
      businessName: (data['businessName'] as String?) ?? '',
      title: (data['title'] as String?) ?? '',
      discountPercent: ((data['discountPercent'] as num?) ?? 0).toInt(),
      startTime:
          (data['startTime'] as Timestamp?)?.toDate() ?? DateTime.now(),
      endTime: (data['endTime'] as Timestamp?)?.toDate() ?? DateTime.now(),
      active: (data['active'] as bool?) ?? false,
      maxRedemptions: ((data['maxRedemptions'] as num?) ?? 0).toInt(),
      redemptionCount: ((data['redemptionCount'] as num?) ?? 0).toInt(),
      createdAt:
          (data['createdAt'] as Timestamp?)?.toDate() ?? DateTime.now(),
      dailyStartMinute: (data['dailyStartMinute'] as num?)?.toInt(),
      dailyEndMinute: (data['dailyEndMinute'] as num?)?.toInt(),
    );
  }

  static Map<String, dynamic> toMap(Offer offer) => <String, dynamic>{
        'businessId': offer.businessId,
        'businessName': offer.businessName,
        'title': offer.title,
        'discountPercent': offer.discountPercent,
        'startTime': Timestamp.fromDate(offer.startTime),
        'endTime': Timestamp.fromDate(offer.endTime),
        'active': offer.active,
        'maxRedemptions': offer.maxRedemptions,
        'redemptionCount': offer.redemptionCount,
        'createdAt': Timestamp.fromDate(offer.createdAt),
        'dailyStartMinute': offer.dailyStartMinute,
        'dailyEndMinute': offer.dailyEndMinute,
      };
}
