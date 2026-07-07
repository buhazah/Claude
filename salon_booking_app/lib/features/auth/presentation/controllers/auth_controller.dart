import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../domain/entities/app_user.dart';
import '../providers/auth_providers.dart';

/// UI state for the sign-in flows (phone OTP handshake + email form).
class AuthFlowState {
  const AuthFlowState({
    this.submitting = false,
    this.verificationId,
    this.phoneNumber,
    this.error,
  });

  final bool submitting;

  /// Set once the SMS code has been sent; the login screen navigates to the
  /// OTP screen when this becomes non-null.
  final String? verificationId;
  final String? phoneNumber;
  final String? error;

  AuthFlowState copyWith({
    bool? submitting,
    String? verificationId,
    String? phoneNumber,
    String? error,
  }) =>
      AuthFlowState(
        submitting: submitting ?? this.submitting,
        verificationId: verificationId ?? this.verificationId,
        phoneNumber: phoneNumber ?? this.phoneNumber,
        error: error,
      );
}

class AuthController extends Notifier<AuthFlowState> {
  @override
  AuthFlowState build() => const AuthFlowState();

  Future<void> sendOtp(String phoneNumber) async {
    state = state.copyWith(submitting: true, error: null);
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
    state = state.copyWith(submitting: true, error: null);
    try {
      await ref.read(authRepositoryProvider).signInWithOtp(
            verificationId: verificationId,
            smsCode: smsCode,
          );
      // Success: currentUserProvider emits and the router redirects.
      state = const AuthFlowState();
    } on Exception catch (e) {
      state = state.copyWith(submitting: false, error: e.toString());
    }
  }

  Future<void> signInWithEmail(String email, String password) async {
    state = state.copyWith(submitting: true, error: null);
    try {
      await ref
          .read(authRepositoryProvider)
          .signInWithEmail(email: email, password: password);
      state = const AuthFlowState();
    } on Exception catch (e) {
      state = state.copyWith(submitting: false, error: e.toString());
    }
  }

  Future<void> registerWithEmail(String email, String password) async {
    state = state.copyWith(submitting: true, error: null);
    try {
      await ref
          .read(authRepositoryProvider)
          .registerWithEmail(email: email, password: password);
      state = const AuthFlowState();
    } on Exception catch (e) {
      state = state.copyWith(submitting: false, error: e.toString());
    }
  }

  Future<void> completeProfile({
    required String name,
    required UserRole role,
  }) async {
    state = state.copyWith(submitting: true, error: null);
    try {
      await ref
          .read(authRepositoryProvider)
          .completeProfile(name: name, role: role);
      state = const AuthFlowState();
    } on Exception catch (e) {
      state = state.copyWith(submitting: false, error: e.toString());
    }
  }

  Future<void> signOut() => ref.read(authRepositoryProvider).signOut();

  /// Back-navigation from the OTP screen restarts the phone flow.
  void resetPhoneFlow() => state = const AuthFlowState();
}

final authControllerProvider =
    NotifierProvider<AuthController, AuthFlowState>(AuthController.new);
