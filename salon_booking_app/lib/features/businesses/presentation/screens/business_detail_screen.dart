import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/errors/error_text.dart';
import '../../../../core/router/route_names.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/formatters.dart';
import '../../../../core/widgets/async_value_view.dart';
import '../../../../core/widgets/empty_state.dart';
import '../../../../core/widgets/rating_badge.dart';
import '../../../offers/domain/services/offer_pricing.dart';
import '../../../offers/presentation/providers/offer_providers.dart';
import '../../domain/entities/business.dart';
import '../../domain/entities/service_offering.dart';
import '../providers/business_providers.dart';

/// Business page: gallery, rating, live offer banner, services list.
/// Tapping "Book" on a service starts the booking flow (tap 1 of 3).
class BusinessDetailScreen extends ConsumerWidget {
  const BusinessDetailScreen({super.key, required this.businessId});

  final String businessId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final businessAsync = ref.watch(businessProvider(businessId));

    return Scaffold(
      body: AsyncValueView(
        value: businessAsync,
        onRetry: () => ref.invalidate(businessProvider(businessId)),
        data: (business) {
          if (business == null) {
            return const EmptyState(
              icon: Icons.storefront_outlined,
              title: 'Salon not found',
            );
          }
          return _BusinessDetailBody(business: business);
        },
      ),
    );
  }
}

class _BusinessDetailBody extends ConsumerWidget {
  const _BusinessDetailBody({required this.business});

  final Business business;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final services = ref.watch(businessServicesProvider(business.id));
    final offers = ref.watch(businessOffersProvider(business.id));
    final liveOffer = OfferPricing.bestLiveOffer(
        offers.valueOrNull ?? const [], business.id);

    return CustomScrollView(
      slivers: [
        SliverAppBar(
          expandedHeight: 220,
          pinned: true,
          flexibleSpace: FlexibleSpaceBar(
            background: business.coverImage == null
                ? Container(
                    color: AppColors.primary.withValues(alpha: 0.1),
                    child: const Icon(Icons.spa_rounded,
                        size: 72, color: AppColors.primary),
                  )
                : PageView(
                    children: [
                      for (final image in business.images)
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
                        business.name,
                        style: Theme.of(context)
                            .textTheme
                            .headlineSmall
                            ?.copyWith(fontWeight: FontWeight.w800),
                      ),
                    ),
                    RatingBadge(
                        rating: business.rating,
                        count: business.ratingCount),
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
                        '${business.address}, ${business.city} · '
                        '${business.audience.label}',
                        style:
                            const TextStyle(color: AppColors.textSecondary),
                      ),
                    ),
                  ],
                ),
                if (business.description.isNotEmpty) ...[
                  const SizedBox(height: 12),
                  Text(business.description),
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
                            'off. Applied automatically at booking.',
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
              message: errorText(error),
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
                      business: business,
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
    required this.business,
    required this.service,
    this.discountPercent,
  });

  final Business business;
  final ServiceOffering service;
  final int? discountPercent;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final hasDiscount = discountPercent != null && discountPercent! > 0;
    final discounted = hasDiscount
        ? service.price.discountedBy(discountPercent!)
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
                  .push(RouteNames.bookService(business.id, service.id)),
              child: const Text('Book'),
            ),
          ],
        ),
      ),
    );
  }
}
