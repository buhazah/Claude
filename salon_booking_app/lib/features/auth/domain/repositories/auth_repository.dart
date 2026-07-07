import '../entities/app_user.dart';

/// Callbacks for the async phone-verification handshake.
typedef CodeSentCallback = void Function(String verificationId);
typedef VerificationFailedCallback = void Function(String message);

/// Contract for authentication + user profile persistence.
///
/// The presentation layer depends only on this interface; the Firebase
/// implementation lives in `data/`. Swapping the auth backend (or faking it
/// in tests) never touches UI code.
abstract interface class AuthRepository {
  /// Emits the signed-in user's profile document (or null when signed out).
  /// Also emits when the profile changes, e.g. right after role selection.
  Stream<AppUser?> watchCurrentUser();

  /// Fires the SMS code. [onCodeSent] receives the verificationId needed by
  /// [signInWithOtp]. On devices with auto-retrieval, sign-in may complete
  /// without an explicit OTP entry — watchCurrentUser will emit.
  Future<void> sendOtp({
    required String phoneNumber,
    required CodeSentCallback onCodeSent,
    required VerificationFailedCallback onFailed,
  });

  Future<void> signInWithOtp({
    required String verificationId,
    required String smsCode,
  });

  Future<void> signInWithEmail({required String email, required String password});

  Future<void> registerWithEmail({required String email, required String password});

  /// Creates/completes the Firestore profile after first sign-in.
  Future<void> completeProfile({required String name, required UserRole role});

  Future<void> signOut();
}
