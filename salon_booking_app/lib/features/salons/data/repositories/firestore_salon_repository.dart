import 'package:cloud_firestore/cloud_firestore.dart';

import '../../../../core/constants/firestore_collections.dart';
import '../../../../core/errors/app_exception.dart';
import '../../domain/entities/blocked_slot.dart';
import '../../domain/entities/salon.dart';
import '../../domain/entities/salon_filters.dart';
import '../../domain/entities/salon_service.dart';
import '../../domain/entities/working_hours.dart';
import '../../domain/repositories/salon_repository.dart';
import '../models/salon_model.dart';
import '../models/service_model.dart';

/// Firestore-backed [SalonRepository].
class FirestoreSalonRepository implements SalonRepository {
  FirestoreSalonRepository({required FirebaseFirestore firestore})
      : _firestore = firestore;

  final FirebaseFirestore _firestore;

  CollectionReference<Map<String, dynamic>> get _salons =>
      _firestore.collection(FirestoreCollections.salons);

  CollectionReference<Map<String, dynamic>> get _services =>
      _firestore.collection(FirestoreCollections.services);

  CollectionReference<Map<String, dynamic>> _blockedSlots(String salonId) =>
      _salons.doc(salonId).collection(FirestoreCollections.blockedSlots);

  @override
  Stream<List<Salon>> watchSalons(SalonFilters filters) {
    Query<Map<String, dynamic>> query = _salons;
    if (filters.audience != null) {
      query = query.where('type', isEqualTo: filters.audience!.value);
    }
    // Rating sort keeps the best salons on top; "nearby" ordering is applied
    // client-side from coordinates (see homeSalonsProvider).
    query = query.orderBy('rating', descending: true).limit(50);

    return query.snapshots().map(
          (snap) => snap.docs
              .map(SalonModel.fromDoc)
              .where(filters.matches)
              .toList(),
        );
  }

  @override
  Stream<Salon?> watchSalon(String salonId) => _salons
      .doc(salonId)
      .snapshots()
      .map((doc) => doc.exists ? SalonModel.fromDoc(doc) : null);

  @override
  Stream<Salon?> watchOwnerSalon(String ownerId) => _salons
      .where('ownerId', isEqualTo: ownerId)
      .limit(1)
      .snapshots()
      .map((snap) =>
          snap.docs.isEmpty ? null : SalonModel.fromDoc(snap.docs.first));

  @override
  Future<String> createSalon({
    required String ownerId,
    required String name,
    required String description,
    required String address,
    required String city,
    required SalonAudience audience,
    required double latitude,
    required double longitude,
  }) async {
    try {
      final salon = Salon(
        id: '',
        ownerId: ownerId,
        name: name,
        description: description,
        address: address,
        city: city,
        latitude: latitude,
        longitude: longitude,
        images: const [],
        rating: 0,
        ratingCount: 0,
        audience: audience,
        startingPrice: 0,
        workingHours: WeeklyHours.standard(),
        createdAt: DateTime.now(),
      );
      final doc = await _salons.add(SalonModel.toMap(salon));
      return doc.id;
    } on FirebaseException catch (e) {
      throw DataException(e.message ?? 'Could not create the salon.');
    }
  }

  @override
  Future<void> updateWorkingHours(String salonId, WeeklyHours hours) async {
    try {
      await _salons
          .doc(salonId)
          .update({'workingHours': SalonModel.hoursToMap(hours)});
    } on FirebaseException catch (e) {
      throw DataException(e.message ?? 'Could not update working hours.');
    }
  }

  // --- Services ---------------------------------------------------------

  @override
  Stream<List<SalonService>> watchServices(String salonId) => _services
      .where('salonId', isEqualTo: salonId)
      .orderBy('name')
      .snapshots()
      .map((snap) => snap.docs.map(ServiceModel.fromDoc).toList());

  @override
  Future<void> addService(SalonService service) async {
    try {
      await _services.add(ServiceModel.toMap(service));
      await _syncStartingPrice(service.salonId);
    } on FirebaseException catch (e) {
      throw DataException(e.message ?? 'Could not add the service.');
    }
  }

  @override
  Future<void> updateService(SalonService service) async {
    try {
      await _services.doc(service.id).update(ServiceModel.toMap(service));
      await _syncStartingPrice(service.salonId);
    } on FirebaseException catch (e) {
      throw DataException(e.message ?? 'Could not update the service.');
    }
  }

  @override
  Future<void> deleteService(String serviceId, String salonId) async {
    try {
      await _services.doc(serviceId).delete();
      await _syncStartingPrice(salonId);
    } on FirebaseException catch (e) {
      throw DataException(e.message ?? 'Could not delete the service.');
    }
  }

  /// Keeps the salon's denormalized `startingPrice` in sync with its
  /// cheapest service. Client-side for the MVP; move to the
  /// `onServiceWritten` Cloud Function when write volume grows.
  Future<void> _syncStartingPrice(String salonId) async {
    final snap = await _services
        .where('salonId', isEqualTo: salonId)
        .orderBy('price')
        .limit(1)
        .get();
    final startingPrice = snap.docs.isEmpty
        ? 0.0
        : ((snap.docs.first.data()['price'] as num?) ?? 0).toDouble();
    await _salons.doc(salonId).update({'startingPrice': startingPrice});
  }

  // --- Blocked slots ------------------------------------------------------

  @override
  Stream<List<BlockedSlot>> watchBlockedSlots(String salonId) =>
      _blockedSlots(salonId).orderBy('start').snapshots().map(
            (snap) => snap.docs.map((doc) {
              final data = doc.data();
              return BlockedSlot(
                id: doc.id,
                start: (data['start'] as Timestamp).toDate(),
                end: (data['end'] as Timestamp).toDate(),
                reason: (data['reason'] as String?) ?? '',
              );
            }).toList(),
          );

  @override
  Future<void> addBlockedSlot(
    String salonId,
    DateTime start,
    DateTime end, {
    String reason = '',
  }) async {
    try {
      await _blockedSlots(salonId).add(<String, dynamic>{
        'start': Timestamp.fromDate(start),
        'end': Timestamp.fromDate(end),
        'reason': reason,
      });
    } on FirebaseException catch (e) {
      throw DataException(e.message ?? 'Could not block the time slot.');
    }
  }

  @override
  Future<void> removeBlockedSlot(String salonId, String slotId) async {
    try {
      await _blockedSlots(salonId).doc(slotId).delete();
    } on FirebaseException catch (e) {
      throw DataException(e.message ?? 'Could not unblock the time slot.');
    }
  }
}
