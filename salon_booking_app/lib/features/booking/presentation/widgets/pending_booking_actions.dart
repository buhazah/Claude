import 'package:flutter/material.dart';

import '../../../../core/theme/app_colors.dart';

/// Accept / Reject row for pending bookings — shared by the owner
/// dashboard and the owner bookings inbox so they can never drift.
class PendingBookingActions extends StatelessWidget {
  const PendingBookingActions({
    super.key,
    required this.onAccept,
    required this.onReject,
  });

  final VoidCallback onAccept;
  final VoidCallback onReject;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: OutlinedButton(
            style: OutlinedButton.styleFrom(
              minimumSize: const Size(0, 42),
              foregroundColor: AppColors.danger,
            ),
            onPressed: onReject,
            child: const Text('Reject'),
          ),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: FilledButton(
            style: FilledButton.styleFrom(minimumSize: const Size(0, 42)),
            onPressed: onAccept,
            child: const Text('Accept'),
          ),
        ),
      ],
    );
  }
}
