/// Typed exceptions thrown by the data layer and surfaced by controllers.
///
/// Repositories catch platform/SDK errors (FirebaseException etc.) and
/// rethrow one of these so the presentation layer never depends on
/// Firebase types.
sealed class AppException implements Exception {
  const AppException(this.message);

  /// Human-readable, safe to show in a SnackBar.
  final String message;

  @override
  String toString() => message;
}

class AuthException extends AppException {
  const AuthException(super.message);
}

class DataException extends AppException {
  const DataException(super.message);
}

class PermissionException extends AppException {
  const PermissionException(super.message);
}

/// A booking conflict (slot taken between selection and confirmation).
class SlotUnavailableException extends AppException {
  const SlotUnavailableException()
      : super('That time slot was just taken. Please pick another one.');
}
