/// A unit of bookable capacity: a chair, a room, a staff member.
///
/// The MVP treats resources as interchangeable — a slot is available while
/// fewer than `resources.count` bookings overlap it. Named resources exist
/// now so per-staff booking (customer picks a stylist) is a UI feature
/// later, not a data migration.
class BookableResource {
  const BookableResource({
    required this.id,
    required this.businessId,
    required this.name,
  });

  final String id;
  final String businessId;
  final String name;
}
