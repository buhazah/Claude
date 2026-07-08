import 'app_exception.dart';

/// Maps any thrown object to copy that is safe to show a user.
///
/// Only [AppException]s carry user-facing messages; everything else
/// (SDK errors, cast failures, Riverpod plumbing) is developer text and
/// must never leak into a SnackBar.
String errorText(Object? error) {
  if (error is AppException) return error.message;
  return 'Something went wrong. Please try again.';
}
