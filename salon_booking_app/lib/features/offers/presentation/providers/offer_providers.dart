import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/di/firebase_providers.dart';
import '../../data/repositories/firestore_offer_repository.dart';
import '../../domain/entities/offer.dart';
import '../../domain/repositories/offer_repository.dart';

final offerRepositoryProvider = Provider<OfferRepository>(
  (ref) => FirestoreOfferRepository(firestore: ref.watch(firestoreProvider)),
);

/// "Hot deals" — offers live right now, best discount first.
final liveOffersProvider = StreamProvider<List<Offer>>((ref) {
  final now = DateTime.now();
  return ref.watch(offerRepositoryProvider).watchLiveOffers().map(
        (offers) => offers.where((o) => o.isLiveAt(now)).toList()
          ..sort((a, b) => b.discountPercent.compareTo(a.discountPercent)),
      );
});

/// One salon's offers (owner management + salon detail banner).
final salonOffersProvider = StreamProvider.family<List<Offer>, String>(
  (ref, salonId) =>
      ref.watch(offerRepositoryProvider).watchSalonOffers(salonId),
);
