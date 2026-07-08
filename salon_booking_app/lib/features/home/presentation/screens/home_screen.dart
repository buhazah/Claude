import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/errors/error_text.dart';
import '../../../../core/router/route_names.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/widgets/empty_state.dart';
import '../../../../core/widgets/section_header.dart';
import '../../../auth/presentation/providers/auth_providers.dart';
import '../../../businesses/presentation/providers/business_providers.dart';
import '../../../offers/presentation/providers/offer_providers.dart';
import '../providers/home_providers.dart';
import '../widgets/business_card.dart';
import '../widgets/filter_sheet.dart';
import '../widgets/offer_card.dart';

/// Customer home: hot deals carousel + nearby salons with filters.
/// Built as slivers so the business list renders lazily, with load-more
/// when the user nears the bottom.
class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(currentUserProvider).valueOrNull;
    final businesses = ref.watch(nearbyBusinessesProvider);
    final offers = ref.watch(liveOffersProvider);
    final filters = ref.watch(discoveryFiltersProvider);
    final limit = ref.watch(discoveryLimitProvider);

    return Scaffold(
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Hi${user != null && user.name.isNotEmpty ? ', ${user.name.split(' ').first}' : ''} 👋',
              style: const TextStyle(
                  fontSize: 14, color: AppColors.textSecondary),
            ),
            const Text('Find your salon'),
          ],
        ),
        toolbarHeight: 72,
        actions: [
          IconButton(
            onPressed: () => FilterSheet.show(context),
            icon: Badge(
              isLabelVisible: !filters.isDefault,
              child: const Icon(Icons.tune_rounded),
            ),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(nearbyBusinessesProvider);
          ref.invalidate(liveOffersProvider);
        },
        child: NotificationListener<ScrollNotification>(
          onNotification: (notification) {
            // Load more when the user nears the bottom and the current page
            // is full (i.e. there may be more to fetch).
            final metrics = notification.metrics;
            final nearBottom =
                metrics.pixels >= metrics.maxScrollExtent - 400;
            final pageFull =
                (businesses.valueOrNull?.length ?? 0) >= limit;
            if (nearBottom && pageFull) {
              ref.read(discoveryLimitProvider.notifier).loadMore();
            }
            return false;
          },
          child: CustomScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            slivers: [
              // --- Hot deals ---------------------------------------------
              SliverToBoxAdapter(
                child: offers.maybeWhen(
                  data: (deals) => deals.isEmpty
                      ? const SizedBox.shrink()
                      : Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const SectionHeader(
                                title: '🔥 Hot deals near you'),
                            SizedBox(
                              height: 148,
                              child: ListView.separated(
                                scrollDirection: Axis.horizontal,
                                padding: const EdgeInsets.symmetric(
                                    horizontal: 20),
                                itemCount: deals.length,
                                separatorBuilder: (_, __) =>
                                    const SizedBox(width: 12),
                                itemBuilder: (context, index) => OfferCard(
                                  offer: deals[index],
                                  onTap: () => context.push(
                                    RouteNames.businessDetail(
                                        deals[index].businessId),
                                  ),
                                ),
                              ),
                            ),
                          ],
                        ),
                  orElse: () => const SizedBox.shrink(),
                ),
              ),

              // --- Nearby businesses --------------------------------------
              const SliverToBoxAdapter(
                child: SectionHeader(title: 'Salons near you'),
              ),
              ...businesses.when(
                loading: () => [
                  const SliverFillRemaining(
                    hasScrollBody: false,
                    child: Center(child: CircularProgressIndicator()),
                  ),
                ],
                error: (error, _) => [
                  SliverFillRemaining(
                    hasScrollBody: false,
                    child: EmptyState(
                      icon: Icons.wifi_off_rounded,
                      title: 'Something went wrong',
                      message: errorText(error),
                      actionLabel: 'Retry',
                      onAction: () =>
                          ref.invalidate(nearbyBusinessesProvider),
                    ),
                  ),
                ],
                data: (items) => items.isEmpty
                    ? [
                        const SliverFillRemaining(
                          hasScrollBody: false,
                          child: EmptyState(
                            icon: Icons.search_off_rounded,
                            title: 'No salons match your filters',
                            message:
                                'Try widening the price range or rating.',
                          ),
                        ),
                      ]
                    : [
                        SliverPadding(
                          padding: const EdgeInsets.fromLTRB(20, 0, 20, 24),
                          sliver: SliverList.separated(
                            itemCount: items.length,
                            separatorBuilder: (_, __) =>
                                const SizedBox(height: 14),
                            itemBuilder: (context, index) => BusinessCard(
                              business: items[index].business,
                              distanceKm: items[index].distanceKm,
                              onTap: () => context.push(
                                RouteNames.businessDetail(
                                    items[index].business.id),
                              ),
                            ),
                          ),
                        ),
                      ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
