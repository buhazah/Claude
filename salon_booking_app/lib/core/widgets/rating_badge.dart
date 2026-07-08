import 'package:flutter/material.dart';

import '../design_system/components/app_rating_badge.dart';

/// Legacy alias for the design-system rating badge.
class RatingBadge extends StatelessWidget {
  const RatingBadge({super.key, required this.rating, this.count});

  final double rating;
  final int? count;

  @override
  Widget build(BuildContext context) =>
      AppRatingBadge(rating: rating, count: count);
}
