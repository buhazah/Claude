import 'package:flutter/material.dart';

import '../design_system/components/app_bottom_sheet.dart';

/// Legacy alias for the design-system bottom sheet.
Future<T?> showAppSheet<T>({
  required BuildContext context,
  required String title,
  required WidgetBuilder builder,
}) =>
    showAppBottomSheet<T>(context: context, title: title, builder: builder);
