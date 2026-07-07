import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../booking/domain/entities/booking.dart';
import '../../../booking/presentation/providers/booking_providers.dart';
import '../../../offers/domain/entities/offer.dart';
import '../../../offers/presentation/providers/offer_providers.dart';
import '../../../salons/domain/entities/salon.dart';
import '../../../salons/domain/entities/salon_service.dart';
import '../../../salons/domain/entities/working_hours.dart';
import '../../../salons/presentation/providers/salon_providers.dart';

/// Today's bookings for the owner's salon (dashboard + schedule).
final ownerTodayBookingsProvider = StreamProvider<List<Booking>>((ref) {
  final salon = ref.watch(ownerSalonProvider).valueOrNull;
  if (salon == null) return Stream.value(const []);
  final now = DateTime.now();
  return ref
      .watch(bookingRepositoryProvider)
      .watchSalonBookingsForDay(salon.id, DateTime(now.year, now.month, now.day));
});

/// Pending booking requests awaiting accept/reject.
final ownerPendingBookingsProvider = StreamProvider<List<Booking>>((ref) {
  final salon = ref.watch(ownerSalonProvider).valueOrNull;
  if (salon == null) return Stream.value(const []);
  return ref.watch(bookingRepositoryProvider).watchSalonBookingsByStatus(
        salon.id,
        BookingStatus.pending,
      );
});

/// All actions an owner performs, behind one facade so screens stay dumb.
final ownerActionsProvider = Provider<OwnerActions>(OwnerActions.new);

class OwnerActions {
  OwnerActions(this._ref);
  final Ref _ref;

  // --- Salon ---
  Future<String> createSalon({
    required String ownerId,
    required String name,
    required String description,
    required String address,
    required String city,
    required SalonAudience audience,
    required double latitude,
    required double longitude,
  }) =>
      _ref.read(salonRepositoryProvider).createSalon(
            ownerId: ownerId,
            name: name,
            description: description,
            address: address,
            city: city,
            audience: audience,
            latitude: latitude,
            longitude: longitude,
          );

  Future<void> updateWorkingHours(String salonId, WeeklyHours hours) =>
      _ref.read(salonRepositoryProvider).updateWorkingHours(salonId, hours);

  // --- Services ---
  Future<void> saveService(SalonService service) {
    final repo = _ref.read(salonRepositoryProvider);
    return service.id.isEmpty
        ? repo.addService(service)
        : repo.updateService(service);
  }

  Future<void> deleteService(String serviceId, String salonId) =>
      _ref.read(salonRepositoryProvider).deleteService(serviceId, salonId);

  // --- Bookings ---
  Future<void> acceptBooking(String bookingId) => _ref
      .read(bookingRepositoryProvider)
      .updateStatus(bookingId, BookingStatus.confirmed);

  Future<void> rejectBooking(String bookingId) => _ref
      .read(bookingRepositoryProvider)
      .updateStatus(bookingId, BookingStatus.cancelled);

  Future<void> completeBooking(String bookingId) => _ref
      .read(bookingRepositoryProvider)
      .updateStatus(bookingId, BookingStatus.completed);

  // --- Offers ---
  Future<void> createOffer(Offer offer) =>
      _ref.read(offerRepositoryProvider).createOffer(offer);

  Future<void> setOfferActive(String offerId, bool active) =>
      _ref.read(offerRepositoryProvider).setActive(offerId, active);

  Future<void> deleteOffer(String offerId) =>
      _ref.read(offerRepositoryProvider).deleteOffer(offerId);

  // --- Availability ---
  Future<void> blockSlot(
    String salonId,
    DateTime start,
    DateTime end,
    String reason,
  ) =>
      _ref
          .read(salonRepositoryProvider)
          .addBlockedSlot(salonId, start, end, reason: reason);

  Future<void> unblockSlot(String salonId, String slotId) =>
      _ref.read(salonRepositoryProvider).removeBlockedSlot(salonId, slotId);
}
