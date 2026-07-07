import 'package:cloud_firestore/cloud_firestore.dart';

import '../../domain/entities/booking.dart';

/// Firestore DTO for `bookings/{id}`.
abstract final class BookingModel {
  static Booking fromDoc(DocumentSnapshot<Map<String, dynamic>> doc) {
    final data = doc.data() ?? const <String, dynamic>{};
    final price = ((data['price'] as num?) ?? 0).toDouble();
    return Booking(
      id: doc.id,
      userId: (data['userId'] as String?) ?? '',
      customerName: (data['customerName'] as String?) ?? '',
      salonId: (data['salonId'] as String?) ?? '',
      salonName: (data['salonName'] as String?) ?? '',
      serviceId: (data['serviceId'] as String?) ?? '',
      serviceName: (data['serviceName'] as String?) ?? '',
      price: price,
      originalPrice:
          ((data['originalPrice'] as num?) ?? price).toDouble(),
      durationMinutes: ((data['duration'] as num?) ?? 30).toInt(),
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
        'salonId': booking.salonId,
        'salonName': booking.salonName,
        'serviceId': booking.serviceId,
        'serviceName': booking.serviceName,
        'price': booking.price,
        'originalPrice': booking.originalPrice,
        'duration': booking.durationMinutes,
        'dateTime': Timestamp.fromDate(booking.start),
        'status': booking.status.value,
        'createdAt': Timestamp.fromDate(booking.createdAt),
        'offerId': booking.offerId,
      };
}
