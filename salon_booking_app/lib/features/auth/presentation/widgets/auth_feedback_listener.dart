import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../controllers/auth_controller.dart';

/// Shows auth errors / info messages as SnackBars. Call once from a screen's
/// build — replaces the identical ref.listen block every auth screen used
/// to carry.
void listenForAuthFeedback(BuildContext context, WidgetRef ref) {
  ref.listen(authControllerProvider, (previous, next) {
    final error = next.error;
    if (error != null && error != previous?.error) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(error)));
    }
    final info = next.info;
    if (info != null && info != previous?.info) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(info)));
    }
  });
}
