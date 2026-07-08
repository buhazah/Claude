import 'package:flutter/material.dart';

import '../tokens/app_colors.dart';
import '../tokens/app_motion.dart';
import '../tokens/app_radius.dart';
import '../tokens/app_spacing.dart';

/// Loading skeleton primitives.
///
/// A gentle opacity pulse (no shimmer package, no dependency) — the one
/// looping animation the motion guidelines allow. Renders statically when
/// the platform requests reduced motion.
class AppSkeleton extends StatefulWidget {
  const AppSkeleton({
    super.key,
    this.width,
    this.height = 14,
    this.radius = AppRadius.badge,
  }) : circle = false;

  const AppSkeleton.circle({super.key, required double size})
      : width = size,
        height = size,
        radius = 0,
        circle = true;

  final double? width;
  final double height;
  final double radius;
  final bool circle;

  @override
  State<AppSkeleton> createState() => _AppSkeletonState();
}

class _AppSkeletonState extends State<AppSkeleton>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: AppMotion.skeletonPulse,
  );

  @override
  void initState() {
    super.initState();
    _controller.repeat(reverse: true);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final box = Container(
      width: widget.width,
      height: widget.height,
      decoration: BoxDecoration(
        color: AppColors.skeleton,
        shape: widget.circle ? BoxShape.circle : BoxShape.rectangle,
        borderRadius:
            widget.circle ? null : BorderRadius.circular(widget.radius),
      ),
    );

    if (MediaQuery.of(context).disableAnimations) return box;

    return FadeTransition(
      opacity: Tween(begin: 1.0, end: 0.45).animate(
        CurvedAnimation(parent: _controller, curve: Curves.easeInOut),
      ),
      child: box,
    );
  }
}

/// Card-shaped placeholder matching [AppBusinessCard]'s silhouette, for
/// discovery-list loading.
class AppSkeletonCard extends StatelessWidget {
  const AppSkeletonCard({super.key});

  @override
  Widget build(BuildContext context) {
    return Card(
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const AspectRatio(
            aspectRatio: 16 / 8,
            child: AppSkeleton(height: double.infinity, radius: 0),
          ),
          Padding(
            padding: const EdgeInsets.all(AppSpacing.lg - 2),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: const [
                AppSkeleton(width: 160, height: 16),
                SizedBox(height: AppSpacing.sm + 2),
                AppSkeleton(width: 220, height: 12),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// A column of [count] skeleton cards — drop-in loading state for list
/// screens.
class AppSkeletonList extends StatelessWidget {
  const AppSkeletonList({super.key, this.count = 3});

  final int count;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        for (var i = 0; i < count; i++) ...[
          const AppSkeletonCard(),
          if (i < count - 1) const SizedBox(height: AppSpacing.lg - 2),
        ],
      ],
    );
  }
}
