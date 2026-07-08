import 'package:flutter/material.dart';

import '../tokens/app_spacing.dart';
import '../tokens/app_typography.dart';

/// The system modal bottom sheet: rounded top (from the theme), drag
/// handle, title, scrollable keyboard-aware content.
///
/// All modal sheets in the app go through this — never raw
/// showModalBottomSheet — so radius, handle, and padding stay uniform.
Future<T?> showAppBottomSheet<T>({
  required BuildContext context,
  required String title,
  required WidgetBuilder builder,
}) {
  return showModalBottomSheet<T>(
    context: context,
    isScrollControlled: true,
    builder: (context) => Padding(
      padding: EdgeInsets.only(
        left: AppSpacing.xl,
        right: AppSpacing.xl,
        bottom: MediaQuery.of(context).viewInsets.bottom + AppSpacing.xl,
      ),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: AppTypography.title),
            const SizedBox(height: AppSpacing.xl),
            builder(context),
          ],
        ),
      ),
    ),
  );
}
