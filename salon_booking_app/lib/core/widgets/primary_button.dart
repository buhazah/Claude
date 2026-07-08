import 'package:flutter/material.dart';

import '../design_system/components/app_button.dart';

/// Legacy alias for the design-system button — existing call sites keep
/// their API; new code uses [AppButton] directly (variants + sizes).
class PrimaryButton extends StatelessWidget {
  const PrimaryButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.loading = false,
    this.icon,
  });

  final String label;
  final VoidCallback? onPressed;
  final bool loading;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    return AppButton(
      label: label,
      onPressed: onPressed,
      loading: loading,
      icon: icon,
    );
  }
}
