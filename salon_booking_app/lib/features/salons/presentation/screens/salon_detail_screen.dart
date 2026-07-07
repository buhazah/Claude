import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/router/route_names.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/formatters.dart';
import '../../../../core/widgets/async_value_view.dart';
import '../../../../core/widgets/empty_state.dart';
import '../../../../core/widgets/rating_badge.dart';
import '../../../offers/domain/services/offer_pricing.dart';
import '../../../offers/presentation/providers/offer_providers.dart';
import '../../domain/entities/salon.dart';
import '../../domain/entities/salon_service.dart';
import '../providers/salon_providers.dart';

/// Salon page: gallery, rating, live offer banner, opening hours and the
/// services list. Tapping "Book" on a service starts the booking flow
/// (tap 1 of 3).
class SalonDetailScreen extends ConsumerWidget {
  const SalonDetailScreen({super.key, required this.salonId});

  final String salonId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final salonAsync = ref.watch(salonProvider(salonId));

    return Scaffold(
      body: AsyncValueView(
        value: salonAsync,
        onRetry: () => ref.invalidate(salonProvider(salonId)),
        data: (salon) {
          if (salon == null) {
            return const EmptyState(
              icon: Icons.storefront_outlined,
              title: 'Salon not found',
            );
          }
          return _SalonDetailBody(salon: salon);
        },
      ),
    );
  }
}

class _SalonDetailBody extends ConsumerWidget {
  const _SalonDetailBody({required this.salon});

  final Salon salon;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final services = ref.watch(salonServicesProvider(salon.id));
    final offers = ref.watch(salonOffersProvider(salon.id));
    final liveOffer =
        OfferPricing.bestLiveOffer(offers.valueOrNull ?? const [], salon.id);

    return CustomScrollView(
      slivers: [
        SliverAppBar(
          expandedHeight: 220,
          pinned: true,
          flexibleSpace: FlexibleSpaceBar(
            background: salon.coverImage == null
                ? Container(
                    color: AppColors.primary.withValues(alpha: 0.1),
                    child: const Icon(Icons.spa_rounded,
                        size: 72, color: AppColors.primary),
                  )
                : PageView(
                    children: [
                      for (final image in salon.images)
                        CachedNetworkImage(imageUrl: image, fit: BoxFit.cover),
                    ],
                  ),
          ),
        ),
        SliverToBoxAdapter(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        salon.name,
                        style: Theme.of(context)
                            .textTheme
                            .headlineSmall
                            ?.copyWith(fontWeight: FontWeight.w800),
                      ),
                    ),
                    RatingBadge(rating: salon.rating, count: salon.ratingCount),
                  ],
                ),
                const SizedBox(height: 6),
                Row(
                  children: [
                    const Icon(Icons.place_outlined,
                        size: 16, color: AppColors.textSecondary),
                    const SizedBox(width: 4),
                    Expanded(
                      child: Text(
                        '${salon.address}, ${salon.city} · ${salon.audience.label}',
                        style:
                            const TextStyle(color: AppColors.textSecondary),
                      ),
                    ),
                  ],
                ),
                if (salon.description.isNotEmpty) ...[
                  const SizedBox(height: 12),
                  Text(salon.description),
                ],
                if (liveOffer != null) ...[
                  const SizedBox(height: 16),
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: AppColors.accent.withValues(alpha: 0.18),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.local_fire_department_rounded,
                            color: AppColors.warning),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Text(
                            '${liveOffer.title} — ${liveOffer.discountPercent}% '
                            'off until ${Formatters.time(liveOffer.endTime)}. '
                            'Applied automatically at booking.',
                            style:
                                const TextStyle(fontWeight: FontWeight.w600),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
                const SizedBox(height: 24),
                Text(
                  'Services',
                  style: Theme.of(context)
                      .textTheme
                      .titleMedium
                      ?.copyWith(fontWeight: FontWeight.w700),
                ),
              ],
            ),
          ),
        ),
        // Services render inside the CustomScrollView, so async states are
        // handled here with sliver equivalents of AsyncValueView.
        services.when(
          loading: () => const SliverToBoxAdapter(
            child: Padding(
              padding: EdgeInsets.all(32),
              child: Center(child: CircularProgressIndicator()),
            ),
          ),
          error: (error, _) => SliverToBoxAdapter(
            child: EmptyState(
              icon: Icons.wifi_off_rounded,
              title: 'Could not load services',
              message: error.toString(),
            ),
          ),
          data: (items) => items.isEmpty
              ? const SliverToBoxAdapter(
                  child: EmptyState(
                    icon: Icons.design_services_outlined,
                    title: 'No services listed yet',
                  ),
                )
              : SliverPadding(
                  padding: const EdgeInsets.fromLTRB(20, 0, 20, 32),
                  sliver: SliverList.separated(
                    itemCount: items.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 10),
                    itemBuilder: (context, index) => _ServiceTile(
                      salon: salon,
                      service: items[index],
                      discountPercent: liveOffer?.discountPercent,
                    ),
                  ),
                ),
        ),
      ],
    );
  }
}

class _ServiceTile extends ConsumerWidget {
  const _ServiceTile({
    required this.salon,
    required this.service,
    this.discountPercent,
  });

  final Salon salon;
  final SalonService service;
  final int? discountPercent;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final hasDiscount = discountPercent != null && discountPercent! > 0;
    final discounted = hasDiscount
        ? service.price * (100 - discountPercent!) / 100
        : service.price;

    return Card(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(service.name,
                      style: const TextStyle(fontWeight: FontWeight.w600)),
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      Text(
                        Formatters.price(discounted),
                        style: const TextStyle(
                          color: AppColors.primary,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      if (hasDiscount) ...[
                        const SizedBox(width: 6),
                        Text(
                          Formatters.price(service.price),
                          style: const TextStyle(
                            color: AppColors.textSecondary,
                            decoration: TextDecoration.lineThrough,
                            fontSize: 12,
                          ),
                        ),
                      ],
                      const SizedBox(width: 8),
                      Text(
                        '· ${Formatters.duration(service.durationMinutes)}',
                        style: const TextStyle(
                          color: AppColors.textSecondary,
                          fontSize: 13,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            FilledButton(
              style: FilledButton.styleFrom(
                minimumSize: const Size(88, 40),
              ),
              // Tap 1 of the 3-tap booking flow.
              onPressed: () => context
                  .push(RouteNames.bookService(salon.id, service.id)),
              child: const Text('Book'),
            ),
          ],
        ),
      ),
    );
  }
}
