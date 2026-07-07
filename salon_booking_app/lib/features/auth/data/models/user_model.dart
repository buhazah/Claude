import 'package:cloud_firestore/cloud_firestore.dart';

import '../../domain/entities/app_user.dart';

/// Firestore DTO for `users/{id}`. Mapping lives here so the domain entity
/// stays free of Firebase types.
abstract final class UserModel {
  static AppUser fromDoc(DocumentSnapshot<Map<String, dynamic>> doc) {
    final data = doc.data() ?? const <String, dynamic>{};
    return AppUser(
      id: doc.id,
      name: (data['name'] as String?) ?? '',
      phone: (data['phone'] as String?) ?? '',
      email: (data['email'] as String?) ?? '',
      role: UserRole.tryParse(data['role'] as String?),
      createdAt:
          (data['createdAt'] as Timestamp?)?.toDate() ?? DateTime.now(),
    );
  }

  static Map<String, dynamic> toMap(AppUser user) => <String, dynamic>{
        'name': user.name,
        'phone': user.phone,
        'email': user.email,
        'role': user.role?.value,
        'createdAt': Timestamp.fromDate(user.createdAt),
      };
}
