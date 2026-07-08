import 'package:cloud_firestore/cloud_firestore.dart';

import '../../../../core/constants/firestore_collections.dart';
import '../../../../core/errors/app_exception.dart';
import '../../domain/entities/offer.dart';
import '../../domain/repositories/offer_repository.dart';
import '../models/offer_model.dart';

/// Firestore-backed [OfferRepository].
///
/// Note: redemption counting is NOT here — it rides in the booking-creation
/// batch (see FirestoreBookingRepository.createBooking) so a discounted
/// booking and its redemption can never disagree.
class FirestoreOfferRepository implements OfferRepository {
  FirestoreOfferRepository({required FirebaseFirestore firestore})
      : _firestore = firestore;

  final FirebaseFirestore _firestore;

  CollectionReference<Map<String, dynamic>> get _offers =>
      _firestore.collection(FirestoreCollections.offers);

  @override
  Stream<List<Offer>> watchLiveOffers() => _offers
      .where('active', isEqualTo: true)
      .where('endTime', isGreaterThan: Timestamp.now())
      .orderBy('endTime')
      .limit(30)
      .snapshots()
      .map((snap) => snap.docs.map(OfferModel.fromDoc).toList());

  @override
  Stream<List<Offer>> watchBusinessOffers(String businessId) => _offers
      .where('businessId', isEqualTo: businessId)
      .orderBy('createdAt', descending: true)
      .snapshots()
      .map((snap) => snap.docs.map(OfferModel.fromDoc).toList());

  @override
  Future<void> createOffer(Offer offer) async {
    try {
      await _offers.add(OfferModel.toMap(offer));
    } on FirebaseException catch (e) {
      throw DataException(e.message ?? 'Could not create the offer.');
    }
  }

  @override
  Future<void> setActive(String offerId, bool active) async {
    try {
      await _offers.doc(offerId).update({'active': active});
    } on FirebaseException catch (e) {
      throw DataException(e.message ?? 'Could not update the offer.');
    }
  }

  @override
  Future<void> deleteOffer(String offerId) async {
    try {
      await _offers.doc(offerId).delete();
    } on FirebaseException catch (e) {
      throw DataException(e.message ?? 'Could not delete the offer.');
    }
  }
}
