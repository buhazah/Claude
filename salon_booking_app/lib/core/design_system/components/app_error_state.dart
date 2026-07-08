import 'package:flutter/material.dart';

import '../tokens/app_colors.dart';
import 'app_empty_state.dart';

/// Failure placeholder with retry. Message must already be user-safe —
/// pass it through `errorText()` first, never a raw exception string.
class AppErrorState extends StatelessWidget {
  const AppErrorState({
    super.key,
    this.title = 'Something went wrong',
    this.message,
    this.onRetry,
  });

  final String title;
  final String? message;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    return AppEmptyState(
      icon: Icons.wifi_off_rounded,
      title: title,
      message: message,
      actionLabel: onRetry == null ? null : 'Retry',
      onAction: onRetry,
      iconColor: AppColors.danger,
      plateColor: const Color(0xFFFBEBEC),
    );
  }
}
