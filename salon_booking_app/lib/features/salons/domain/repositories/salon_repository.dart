import '../entities/blocked_slot.dart';
import '../entities/salon.dart';
import '../entities/salon_filters.dart';
import '../entities/salon_service.dart';
import '../entities/working_hours.dart';

/// Contract for salon discovery + owner-side salon management.
abstract interface class SalonRepository {
  /// Live list of salons for discovery. [filters.audience] is pushed into
  /// the Firestore query; price/rating are filtered in-memory (MVP scale).
  Stream<List<Salon>> watchSalons(SalonFilters filters);

  Stream<Salon?> watchSalon(String salonId);

  /// The salon owned by [ownerId] (single-salon-per-owner at MVP;
  /// returns the first match so multi-branch can extend later).
  Stream<Salon?> watchOwnerSalon(String ownerId);

  Future<String> createSalon({
    required String ownerId,
    required String name,
    required String description,
    required String address,
    required String city,
    required SalonAudience audience,
    required double latitude,
    required double longitude,
  });

  Future<void> updateWorkingHours(String salonId, WeeklyHours hours);

  // --- Services ---
  Stream<List<SalonService>> watchServices(String salonId);
  Future<void> addService(SalonService service);
  Future<void> updateService(SalonService service);
  Future<void> deleteService(String serviceId, String salonId);

  // --- Blocked slots ---
  Stream<List<BlockedSlot>> watchBlockedSlots(String salonId);
  Future<void> addBlockedSlot(String salonId, DateTime start, DateTime end,
      {String reason});
  Future<void> removeBlockedSlot(String salonId, String slotId);
}
