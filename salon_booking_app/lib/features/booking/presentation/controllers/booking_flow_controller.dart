import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../auth/presentation/providers/auth_providers.dart';
import '../../../offers/domain/entities/offer.dart';
import '../../../offers/domain/services/offer_pricing.dart';
import '../../../offers/presentation/providers/offer_providers.dart';
import '../../../salons/domain/entities/salon.dart';
import '../../../salons/domain/entities/salon_service.dart';
import '../../domain/entities/booking.dart';
import '../../domain/entities/time_slot.dart';
import '../providers/booking_providers.dart';

/// State of the 3-tap booking flow:
/// tap 1 = pick service, tap 2 = pick slot, tap 3 = confirm.
class BookingFlowState {
  const BookingFlowState({
    this.slot,
    this.submitting = false,
    this.confirmedBookingId,
    this.error,
  });

  final TimeSlot? slot;
  final bool submitting;

  /// Set on success — the screen shows the confirmation view.
  final String? confirmedBookingId;
  final String? error;

  BookingFlowState copyWith({
    TimeSlot? Function()? slot,
    bool? submitting,
    String? confirmedBookingId,
    String? error,
  }) =>
      BookingFlowState(
        slot: slot == null ? this.slot : slot(),
        submitting: submitting ?? this.submitting,
        confirmedBookingId: confirmedBookingId ?? this.confirmedBookingId,
        error: error,
      );
}

class BookingFlowController extends AutoDisposeNotifier<BookingFlowState> {
  @override
  BookingFlowState build() => const BookingFlowState();

  void selectSlot(TimeSlot slot) =>
      state = state.copyWith(slot: () => slot, error: null);

  void clearSlot() => state = state.copyWith(slot: () => null);

  /// Creates the pending booking, applying the salon's best live offer.
  Future<void> confirm({
    required Salon salon,
    required SalonService service,
  }) async {
    final slot = state.slot;
    if (slot == null || state.submitting) return;

    final user = ref.read(currentUserProvider).valueOrNull;
    if (user == null) {
      state = state.copyWith(error: 'Please sign in again.');
      return;
    }

    state = state.copyWith(submitting: true, error: null);
    try {
      // Discount is decided at booking time and snapshotted onto the
      // booking document (see OfferPricing docs).
      final offers =
          ref.read(salonOffersProvider(salon.id)).valueOrNull ?? const <Offer>[];
      final offer = OfferPricing.bestLiveOffer(offers, salon.id);
      final price = offer == null
          ? service.price
          : OfferPricing.discountedPrice(service.price, offer);

      final booking = Booking(
        id: '',
        userId: user.id,
        customerName: user.name,
        salonId: salon.id,
        salonName: salon.name,
        serviceId: service.id,
        serviceName: service.name,
        price: price,
        originalPrice: service.price,
        durationMinutes: service.durationMinutes,
        start: slot.start,
        status: BookingStatus.pending,
        createdAt: DateTime.now(),
        offerId: offer?.id,
      );

      final id =
          await ref.read(bookingRepositoryProvider).createBooking(booking);
      if (offer != null) {
        await ref.read(offerRepositoryProvider).incrementRedemption(offer.id);
      }
      state = state.copyWith(submitting: false, confirmedBookingId: id);
    } on Exception catch (e) {
      state = state.copyWith(submitting: false, error: e.toString());
    }
  }
}

final bookingFlowControllerProvider =
    NotifierProvider.autoDispose<BookingFlowController, BookingFlowState>(
        BookingFlowController.new);

/// Customer-side booking actions outside the flow (cancel from history).
final bookingActionsProvider = Provider<BookingActions>(BookingActions.new);

class BookingActions {
  BookingActions(this._ref);
  final Ref _ref;

  Future<void> cancel(String bookingId) => _ref
      .read(bookingRepositoryProvider)
      .updateStatus(bookingId, BookingStatus.cancelled);
}
