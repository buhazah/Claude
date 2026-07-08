import '../entities/blocked_slot.dart';
import '../entities/bookable_resource.dart';
import '../entities/business.dart';
import '../entities/discovery_filters.dart';
import '../entities/service_offering.dart';
import '../entities/working_hours.dart';

/// Contract for marketplace discovery + owner-side business management.
abstract interface class BusinessRepository {
  /// Live discovery list (approved businesses only). [filters.audience] and
  /// [filters.category] are pushed into the Firestore query; price/rating
  /// are filtered in-memory (MVP scale — move server-side with pagination
  /// + geohash when listings grow).
  Stream<List<Business>> watchBusinesses(DiscoveryFilters filters,
      {int limit});

  Stream<Business?> watchBusiness(String businessId);

  /// All businesses owned by [ownerId] (multi-branch supported).
  Stream<List<Business>> watchOwnerBusinesses(String ownerId);

  /// Creates an UNAPPROVED business (marketplace listing requires admin
  /// approval — see Business.approved). Returns the new id.
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
  });

  Future<void> updateWorkingHours(String businessId, WeeklyHours hours);

  // --- Services ---
  Stream<List<ServiceOffering>> watchServices(String businessId);
  Future<void> addService(ServiceOffering service);
  Future<void> updateService(ServiceOffering service);
  Future<void> deleteService(String serviceId, String businessId);

  // --- Capacity resources (chairs / rooms / staff) ---
  Stream<List<BookableResource>> watchResources(String businessId);
  Future<void> addResource(String businessId, String name);
  Future<void> removeResource(String businessId, String resourceId);

  // --- Blocked slots (upcoming only) ---
  Stream<List<BlockedSlot>> watchUpcomingBlockedSlots(String businessId);
  Future<void> addBlockedSlot(String businessId, DateTime start, DateTime end);
  Future<void> removeBlockedSlot(String businessId, String slotId);
}
