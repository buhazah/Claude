import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../booking/domain/entities/booking.dart';
import '../../../booking/presentation/providers/booking_providers.dart';
import '../../../businesses/domain/entities/business.dart';
import '../../../businesses/domain/entities/service_offering.dart';
import '../../../businesses/domain/entities/working_hours.dart';
import '../../../businesses/presentation/providers/business_providers.dart';
import '../../../offers/domain/entities/offer.dart';
import '../../../offers/presentation/providers/offer_providers.dart';

/// Today's bookings for the owner's active business (dashboard + schedule).
final ownerTodayBookingsProvider = StreamProvider<List<Booking>>((ref) {
  final business = ref.watch(ownerBusinessProvider).valueOrNull;
  if (business == null) return Stream.value(const []);
  final now = DateTime.now();
  return ref.watch(bookingRepositoryProvider).watchOwnerBookingsForDay(
        ownerId: business.ownerId,
        businessId: business.id,
        day: DateTime(now.year, now.month, now.day),
      );
});

/// The owner's bookings on an arbitrary day (schedule tab).
final ownerDayBookingsProvider =
    StreamProvider.family<List<Booking>, DateTime>((ref, day) {
  final business = ref.watch(ownerBusinessProvider).valueOrNull;
  if (business == null) return Stream.value(const []);
  return ref.watch(bookingRepositoryProvider).watchOwnerBookingsForDay(
        ownerId: business.ownerId,
        businessId: business.id,
        day: day,
      );
});

/// Pending booking requests awaiting accept/reject.
final ownerPendingBookingsProvider = StreamProvider<List<Booking>>((ref) {
  final business = ref.watch(ownerBusinessProvider).valueOrNull;
  if (business == null) return Stream.value(const []);
  return ref.watch(bookingRepositoryProvider).watchOwnerBookingsByStatus(
        ownerId: business.ownerId,
        businessId: business.id,
        status: BookingStatus.pending,
      );
});

/// All actions an owner performs, behind one facade so screens stay dumb.
final ownerActionsProvider = Provider<OwnerActions>(OwnerActions.new);

class OwnerActions {
  OwnerActions(this._ref);
  final Ref _ref;

  // --- Business ---
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
  }) =>
      _ref.read(businessRepositoryProvider).createBusiness(
            ownerId: ownerId,
            name: name,
            description: description,
            address: address,
            city: city,
            audience: audience,
            category: category,
            latitude: latitude,
            longitude: longitude,
          );

  Future<void> updateWorkingHours(String businessId, WeeklyHours hours) =>
      _ref
          .read(businessRepositoryProvider)
          .updateWorkingHours(businessId, hours);

  // --- Services ---
  Future<void> saveService(ServiceOffering service) {
    final repo = _ref.read(businessRepositoryProvider);
    return service.id.isEmpty
        ? repo.addService(service)
        : repo.updateService(service);
  }

  Future<void> deleteService(String serviceId, String businessId) => _ref
      .read(businessRepositoryProvider)
      .deleteService(serviceId, businessId);

  // --- Capacity resources ---
  Future<void> addResource(String businessId, String name) =>
      _ref.read(businessRepositoryProvider).addResource(businessId, name);

  Future<void> removeResource(String businessId, String resourceId) => _ref
      .read(businessRepositoryProvider)
      .removeResource(businessId, resourceId);

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
  Future<void> blockSlot(String businessId, DateTime start, DateTime end) =>
      _ref
          .read(businessRepositoryProvider)
          .addBlockedSlot(businessId, start, end);

  Future<void> unblockSlot(String businessId, String slotId) => _ref
      .read(businessRepositoryProvider)
      .removeBlockedSlot(businessId, slotId);
}
