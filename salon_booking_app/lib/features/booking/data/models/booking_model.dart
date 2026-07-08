import 'package:cloud_firestore/cloud_firestore.dart';

import '../../../../core/utils/money.dart';
import '../../domain/entities/booking.dart';

/// Firestore DTO for `bookings/{id}`.
abstract final class BookingModel {
  static Booking fromDoc(DocumentSnapshot<Map<String, dynamic>> doc) {
    final data = doc.data() ?? const <String, dynamic>{};
    final priceFils = ((data['priceFils'] as num?) ?? 0).toInt();
    return Booking(
      id: doc.id,
      userId: (data['userId'] as String?) ?? '',
      customerName: (data['customerName'] as String?) ?? '',
      businessId: (data['businessId'] as String?) ?? '',
      businessName: (data['businessName'] as String?) ?? '',
      ownerId: (data['ownerId'] as String?) ?? '',
      serviceId: (data['serviceId'] as String?) ?? '',
      serviceName: (data['serviceName'] as String?) ?? '',
      price: Money(priceFils),
      originalPrice: Money(
          ((data['originalPriceFils'] as num?) ?? priceFils).toInt()),
      durationMinutes: ((data['durationMinutes'] as num?) ?? 30).toInt(),
      start: (data['dateTime'] as Timestamp?)?.toDate() ?? DateTime.now(),
      status: BookingStatus.parse(data['status'] as String?),
      createdAt:
          (data['createdAt'] as Timestamp?)?.toDate() ?? DateTime.now(),
      offerId: data['offerId'] as String?,
    );
  }

  static Map<String, dynamic> toMap(Booking booking) => <String, dynamic>{
        'userId': booking.userId,
        'customerName': booking.customerName,
        'businessId': booking.businessId,
        'businessName': booking.businessName,
        'ownerId': booking.ownerId,
        'serviceId': booking.serviceId,
        'serviceName': booking.serviceName,
        'priceFils': booking.price.fils,
        'originalPriceFils': booking.originalPrice.fils,
        'durationMinutes': booking.durationMinutes,
        'dateTime': Timestamp.fromDate(booking.start),
        'status': booking.status.value,
        'createdAt': Timestamp.fromDate(booking.createdAt),
        'offerId': booking.offerId,
      };
}
