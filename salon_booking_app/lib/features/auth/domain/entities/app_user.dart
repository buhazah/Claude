/// Roles drive routing: customers get the discovery/booking app,
/// owners get the salon dashboard.
enum UserRole {
  customer('customer'),
  owner('owner');

  const UserRole(this.value);

  /// Value persisted in Firestore (`users.role`).
  final String value;

  static UserRole? tryParse(String? raw) {
    for (final role in UserRole.values) {
      if (role.value == raw) return role;
    }
    return null;
  }
}

/// Domain user — pure Dart, no Firebase types.
class AppUser {
  const AppUser({
    required this.id,
    required this.name,
    required this.phone,
    required this.email,
    required this.role,
    required this.createdAt,
  });

  final String id;
  final String name;
  final String phone;
  final String email;

  /// Null until the user completes role selection during onboarding.
  final UserRole? role;
  final DateTime createdAt;

  bool get isOwner => role == UserRole.owner;
  bool get needsRoleSelection => role == null;

  AppUser copyWith({String? name, UserRole? role}) => AppUser(
        id: id,
        name: name ?? this.name,
        phone: phone,
        email: email,
        role: role ?? this.role,
        createdAt: createdAt,
      );
}
