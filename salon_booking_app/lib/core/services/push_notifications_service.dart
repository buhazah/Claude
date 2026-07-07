import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// FCM wiring, kept behind one service so enabling push is a single call.
///
/// Not invoked yet (notifications are "ready but optional" for the MVP).
/// To enable:
///   1. `await ref.read(pushNotificationsServiceProvider).initialize()`
///      after sign-in (e.g. from the auth controller).
///   2. Persist the token on `users/{uid}.fcmToken`.
///   3. Implement the `onBookingCreated` / `onBookingStatusChanged`
///      Cloud Functions (see firebase/functions/src/index.ts).
class PushNotificationsService {
  PushNotificationsService(this._messaging);

  final FirebaseMessaging _messaging;

  Future<String?> initialize() async {
    final settings = await _messaging.requestPermission();
    if (settings.authorizationStatus == AuthorizationStatus.denied) {
      return null;
    }
    // Token refreshes should also be persisted:
    // _messaging.onTokenRefresh.listen(saveToken);
    return _messaging.getToken();
  }
}

final pushNotificationsServiceProvider = Provider<PushNotificationsService>(
  (ref) => PushNotificationsService(FirebaseMessaging.instance),
);
