import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';

import '../../../../core/constants/firestore_collections.dart';
import '../../../../core/errors/app_exception.dart';
import '../../domain/entities/app_user.dart';
import '../../domain/repositories/auth_repository.dart';
import '../models/user_model.dart';

/// Firebase-backed [AuthRepository].
///
/// Phone auth is the primary flow; email/password is the optional secondary.
/// A `users/{uid}` profile document is created lazily on first sign-in and
/// completed (name + role) by [completeProfile].
class FirebaseAuthRepository implements AuthRepository {
  FirebaseAuthRepository({
    required FirebaseAuth auth,
    required FirebaseFirestore firestore,
  })  : _auth = auth,
        _firestore = firestore;

  final FirebaseAuth _auth;
  final FirebaseFirestore _firestore;

  CollectionReference<Map<String, dynamic>> get _users =>
      _firestore.collection(FirestoreCollections.users);

  @override
  Stream<AppUser?> watchCurrentUser() {
    // Re-subscribe to the profile doc whenever the auth user changes.
    return _auth.authStateChanges().asyncExpand((user) {
      if (user == null) return Stream<AppUser?>.value(null);
      return _users.doc(user.uid).snapshots().map((doc) {
        if (!doc.exists) {
          // Signed in but profile not written yet → onboarding state.
          return AppUser(
            id: user.uid,
            name: '',
            phone: user.phoneNumber ?? '',
            email: user.email ?? '',
            role: null,
            createdAt: DateTime.now(),
          );
        }
        return UserModel.fromDoc(doc);
      });
    });
  }

  @override
  Future<void> sendOtp({
    required String phoneNumber,
    required CodeSentCallback onCodeSent,
    required VerificationFailedCallback onFailed,
  }) async {
    await _auth.verifyPhoneNumber(
      phoneNumber: phoneNumber,
      // Android auto-retrieval: sign in silently when the SMS is captured.
      verificationCompleted: (credential) async {
        try {
          await _auth.signInWithCredential(credential);
        } on FirebaseAuthException catch (e) {
          onFailed(_authMessage(e));
        }
      },
      verificationFailed: (e) => onFailed(_authMessage(e)),
      codeSent: (verificationId, _) => onCodeSent(verificationId),
      codeAutoRetrievalTimeout: (_) {},
    );
  }

  @override
  Future<void> signInWithOtp({
    required String verificationId,
    required String smsCode,
  }) async {
    try {
      final credential = PhoneAuthProvider.credential(
        verificationId: verificationId,
        smsCode: smsCode,
      );
      await _auth.signInWithCredential(credential);
    } on FirebaseAuthException catch (e) {
      throw AuthException(_authMessage(e));
    }
  }

  @override
  Future<void> signInWithEmail({
    required String email,
    required String password,
  }) async {
    try {
      await _auth.signInWithEmailAndPassword(email: email, password: password);
    } on FirebaseAuthException catch (e) {
      throw AuthException(_authMessage(e));
    }
  }

  @override
  Future<void> registerWithEmail({
    required String email,
    required String password,
  }) async {
    try {
      await _auth.createUserWithEmailAndPassword(
        email: email,
        password: password,
      );
    } on FirebaseAuthException catch (e) {
      throw AuthException(_authMessage(e));
    }
  }

  @override
  Future<void> completeProfile({
    required String name,
    required UserRole role,
  }) async {
    final user = _auth.currentUser;
    if (user == null) {
      throw const AuthException('Not signed in.');
    }
    try {
      final profile = AppUser(
        id: user.uid,
        name: name,
        phone: user.phoneNumber ?? '',
        email: user.email ?? '',
        role: role,
        createdAt: DateTime.now(),
      );
      await _users
          .doc(user.uid)
          .set(UserModel.toMap(profile), SetOptions(merge: true));
    } on FirebaseException catch (e) {
      throw DataException(e.message ?? 'Could not save your profile.');
    }
  }

  @override
  Future<void> signOut() => _auth.signOut();

  static String _authMessage(FirebaseAuthException e) => switch (e.code) {
        'invalid-phone-number' => 'That phone number looks invalid.',
        'invalid-verification-code' => 'Wrong code. Please try again.',
        'too-many-requests' => 'Too many attempts. Try again later.',
        'user-not-found' || 'wrong-password' || 'invalid-credential' =>
          'Email or password is incorrect.',
        'email-already-in-use' => 'An account already exists for that email.',
        'weak-password' => 'Password is too weak (min 6 characters).',
        _ => e.message ?? 'Authentication failed. Please try again.',
      };
}
