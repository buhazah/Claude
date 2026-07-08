import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/errors/error_text.dart';
import '../../domain/entities/app_user.dart';
import '../providers/auth_providers.dart';

/// Sentinel so copyWith can distinguish "not passed" from "set to null".
const Object _unset = Object();

/// UI state for the sign-in flows (phone OTP handshake + email form).
class AuthFlowState {
  const AuthFlowState({
    this.submitting = false,
    this.verificationId,
    this.phoneNumber,
    this.error,
    this.info,
  });

  final bool submitting;

  /// Set once the SMS code has been sent; the login screen navigates to the
  /// OTP screen when this becomes non-null.
  final String? verificationId;
  final String? phoneNumber;
  final String? error;

  /// Non-error feedback (e.g. "password reset email sent").
  final String? info;

  AuthFlowState copyWith({
    bool? submitting,
    Object? verificationId = _unset,
    Object? phoneNumber = _unset,
    Object? error = _unset,
    Object? info = _unset,
  }) =>
      AuthFlowState(
        submitting: submitting ?? this.submitting,
        verificationId: identical(verificationId, _unset)
            ? this.verificationId
            : verificationId as String?,
        phoneNumber: identical(phoneNumber, _unset)
            ? this.phoneNumber
            : phoneNumber as String?,
        error: identical(error, _unset) ? this.error : error as String?,
        info: identical(info, _unset) ? this.info : info as String?,
      );
}

class AuthController extends Notifier<AuthFlowState> {
  @override
  AuthFlowState build() => const AuthFlowState();

  Future<void> sendOtp(String phoneNumber) async {
    state = state.copyWith(submitting: true, error: null, info: null);
    await ref.read(authRepositoryProvider).sendOtp(
          phoneNumber: phoneNumber,
          onCodeSent: (verificationId) {
            state = AuthFlowState(
              verificationId: verificationId,
              phoneNumber: phoneNumber,
            );
          },
          onFailed: (message) {
            state = AuthFlowState(error: message);
          },
        );
  }

  Future<void> verifyOtp(String smsCode) async {
    final verificationId = state.verificationId;
    if (verificationId == null) return;
    await _run(() => ref.read(authRepositoryProvider).signInWithOtp(
          verificationId: verificationId,
          smsCode: smsCode,
        ));
  }

  Future<void> signInWithEmail(String email, String password) => _run(
        () => ref
            .read(authRepositoryProvider)
            .signInWithEmail(email: email, password: password),
      );

  Future<void> registerWithEmail(String email, String password) => _run(
        () => ref
            .read(authRepositoryProvider)
            .registerWithEmail(email: email, password: password),
      );

  Future<void> sendPasswordReset(String email) => _run(
        () => ref.read(authRepositoryProvider).sendPasswordReset(email: email),
        successInfo: 'Password reset email sent — check your inbox.',
      );

  Future<void> completeProfile({
    required String name,
    required UserRole role,
  }) =>
      _run(() => ref
          .read(authRepositoryProvider)
          .completeProfile(name: name, role: role));

  Future<void> signOut() => ref.read(authRepositoryProvider).signOut();

  /// Back-navigation from the OTP screen restarts the phone flow.
  void resetPhoneFlow() => state = const AuthFlowState();

  /// Shared submit wrapper: spinner on, run, map errors to safe copy.
  /// On success the auth stream emits and the router redirects.
  Future<void> _run(
    Future<void> Function() action, {
    String? successInfo,
  }) async {
    state = state.copyWith(submitting: true, error: null, info: null);
    try {
      await action();
      state = state.copyWith(submitting: false, info: successInfo);
    } on Exception catch (e) {
      state = state.copyWith(submitting: false, error: errorText(e));
    }
  }
}

final authControllerProvider =
    NotifierProvider<AuthController, AuthFlowState>(AuthController.new);
