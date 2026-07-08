import 'package:cloud_firestore/cloud_firestore.dart';

import '../../../../core/constants/firestore_collections.dart';
import '../../../../core/errors/app_exception.dart';
import '../../../../core/utils/money.dart';
import '../../domain/entities/blocked_slot.dart';
import '../../domain/entities/bookable_resource.dart';
import '../../domain/entities/business.dart';
import '../../domain/entities/discovery_filters.dart';
import '../../domain/entities/service_offering.dart';
import '../../domain/entities/working_hours.dart';
import '../../domain/repositories/business_repository.dart';
import '../models/business_model.dart';
import '../models/service_offering_model.dart';

/// Firestore-backed [BusinessRepository].
class FirestoreBusinessRepository implements BusinessRepository {
  FirestoreBusinessRepository({required FirebaseFirestore firestore})
      : _firestore = firestore;

  final FirebaseFirestore _firestore;

  CollectionReference<Map<String, dynamic>> get _businesses =>
      _firestore.collection(FirestoreCollections.businesses);

  CollectionReference<Map<String, dynamic>> get _services =>
      _firestore.collection(FirestoreCollections.services);

  CollectionReference<Map<String, dynamic>> _resources(String businessId) =>
      _businesses.doc(businessId).collection(FirestoreCollections.resources);

  CollectionReference<Map<String, dynamic>> _blockedSlots(String businessId) =>
      _businesses
          .doc(businessId)
          .collection(FirestoreCollections.blockedSlots);

  @override
  Stream<List<Business>> watchBusinesses(
    DiscoveryFilters filters, {
    int limit = 20,
  }) {
    // Only approved listings surface in discovery (marketplace gate).
    Query<Map<String, dynamic>> query =
        _businesses.where('approved', isEqualTo: true);
    if (filters.audience != null) {
      query = query.where('audience', isEqualTo: filters.audience!.value);
    }
    if (filters.category != null) {
      query = query.where('category', isEqualTo: filters.category!.value);
    }
    query = query.orderBy('rating', descending: true).limit(limit);

    return query.snapshots().map(
          (snap) => snap.docs
              .map(BusinessModel.fromDoc)
              .where(filters.matches)
              .toList(),
        );
  }

  @override
  Stream<Business?> watchBusiness(String businessId) => _businesses
      .doc(businessId)
      .snapshots()
      .map((doc) => doc.exists ? BusinessModel.fromDoc(doc) : null);

  @override
  Stream<List<Business>> watchOwnerBusinesses(String ownerId) => _businesses
      .where('ownerId', isEqualTo: ownerId)
      .snapshots()
      .map((snap) {
        final list = snap.docs.map(BusinessModel.fromDoc).toList()
          ..sort((a, b) => a.createdAt.compareTo(b.createdAt));
        return list;
      });

  @override
  Future<String> createBusiness({
    required String ownerId,
    required String name,
    required String description,
    required String address,
    required String city,
    required Audience audience,
    required BusinessCategory category,
    required double latitude,
    required double longitude,
  }) async {
    try {
      final business = Business(
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
        category: category,
        // Listings go live only after admin approval (see Business.approved).
        approved: false,
        startingPrice: const Money.zero(),
        workingHours: WeeklyHours.standard(),
        createdAt: DateTime.now(),
      );
      final doc = await _businesses.add(BusinessModel.toMap(business));
      return doc.id;
    } on FirebaseException catch (e) {
      throw DataException(e.message ?? 'Could not create the business.');
    }
  }

  @override
  Future<void> updateWorkingHours(String businessId, WeeklyHours hours) async {
    try {
      await _businesses
          .doc(businessId)
          .update({'workingHours': BusinessModel.hoursToMap(hours)});
    } on FirebaseException catch (e) {
      throw DataException(e.message ?? 'Could not update working hours.');
    }
  }

  // --- Services ---------------------------------------------------------

  @override
  Stream<List<ServiceOffering>> watchServices(String businessId) => _services
      .where('businessId', isEqualTo: businessId)
      .orderBy('name')
      .snapshots()
      .map((snap) => snap.docs.map(ServiceOfferingModel.fromDoc).toList());

  @override
  Future<void> addService(ServiceOffering service) async {
    try {
      await _services.add(ServiceOfferingModel.toMap(service));
      await _syncStartingPrice(service.businessId);
    } on FirebaseException catch (e) {
      throw DataException(e.message ?? 'Could not add the service.');
    }
  }

  @override
  Future<void> updateService(ServiceOffering service) async {
    try {
      await _services
          .doc(service.id)
          .update(ServiceOfferingModel.toMap(service));
      await _syncStartingPrice(service.businessId);
    } on FirebaseException catch (e) {
      throw DataException(e.message ?? 'Could not update the service.');
    }
  }

  @override
  Future<void> deleteService(String serviceId, String businessId) async {
    try {
      await _services.doc(serviceId).delete();
      await _syncStartingPrice(businessId);
    } on FirebaseException catch (e) {
      throw DataException(e.message ?? 'Could not delete the service.');
    }
  }

  /// Keeps the business's denormalized `startingPriceFils` in sync with its
  /// cheapest service. Runs on the owner's client (only owners write
  /// services); the `onServiceWritten` Cloud Function performs the same
  /// sync server-side once deployed — both write the same value, so the
  /// duplication is benign.
  Future<void> _syncStartingPrice(String businessId) async {
    final snap = await _services
        .where('businessId', isEqualTo: businessId)
        .orderBy('priceFils')
        .limit(1)
        .get();
    final fils = snap.docs.isEmpty
        ? 0
        : ((snap.docs.first.data()['priceFils'] as num?) ?? 0).toInt();
    await _businesses.doc(businessId).update({'startingPriceFils': fils});
  }

  // --- Resources ----------------------------------------------------------

  @override
  Stream<List<BookableResource>> watchResources(String businessId) =>
      _resources(businessId).orderBy('name').snapshots().map(
            (snap) => snap.docs
                .map((doc) => BookableResource(
                      id: doc.id,
                      businessId: businessId,
                      name: (doc.data()['name'] as String?) ?? '',
                    ))
                .toList(),
          );

  @override
  Future<void> addResource(String businessId, String name) async {
    try {
      await _resources(businessId).add(<String, dynamic>{'name': name});
    } on FirebaseException catch (e) {
      throw DataException(e.message ?? 'Could not add the resource.');
    }
  }

  @override
  Future<void> removeResource(String businessId, String resourceId) async {
    try {
      await _resources(businessId).doc(resourceId).delete();
    } on FirebaseException catch (e) {
      throw DataException(e.message ?? 'Could not remove the resource.');
    }
  }

  // --- Blocked slots ------------------------------------------------------

  @override
  Stream<List<BlockedSlot>> watchUpcomingBlockedSlots(String businessId) =>
      _blockedSlots(businessId)
          .where('end', isGreaterThan: Timestamp.now())
          .orderBy('end')
          .limit(100)
          .snapshots()
          .map(
            (snap) => snap.docs.map((doc) {
              final data = doc.data();
              return BlockedSlot(
                id: doc.id,
                start: (data['start'] as Timestamp).toDate(),
                end: (data['end'] as Timestamp).toDate(),
              );
            }).toList(),
          );

  @override
  Future<void> addBlockedSlot(
    String businessId,
    DateTime start,
    DateTime end,
  ) async {
    try {
      await _blockedSlots(businessId).add(<String, dynamic>{
        'start': Timestamp.fromDate(start),
        'end': Timestamp.fromDate(end),
      });
    } on FirebaseException catch (e) {
      throw DataException(e.message ?? 'Could not block the time slot.');
    }
  }

  @override
  Future<void> removeBlockedSlot(String businessId, String slotId) async {
    try {
      await _blockedSlots(businessId).doc(slotId).delete();
    } on FirebaseException catch (e) {
      throw DataException(e.message ?? 'Could not unblock the time slot.');
    }
  }
}
