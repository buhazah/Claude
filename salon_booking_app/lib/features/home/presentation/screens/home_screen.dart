import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/router/route_names.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/widgets/async_value_view.dart';
import '../../../../core/widgets/empty_state.dart';
import '../../../../core/widgets/section_header.dart';
import '../../../auth/presentation/providers/auth_providers.dart';
import '../../../offers/presentation/providers/offer_providers.dart';
import '../../../salons/presentation/providers/salon_providers.dart';
import '../providers/home_providers.dart';
import '../widgets/filter_sheet.dart';
import '../widgets/offer_card.dart';
import '../widgets/salon_card.dart';

/// Customer home: hot deals carousel + nearby salons with filters.
class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(currentUserProvider).valueOrNull;
    final salons = ref.watch(nearbySalonsProvider);
    final offers = ref.watch(liveOffersProvider);
    final filters = ref.watch(salonFiltersProvider);

    return Scaffold(
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Hi${user != null && user.name.isNotEmpty ? ', ${user.name.split(' ').first}' : ''} 👋',
              style: const TextStyle(fontSize: 14, color: AppColors.textSecondary),
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
          ref.invalidate(nearbySalonsProvider);
          ref.invalidate(liveOffersProvider);
        },
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          children: [
            // --- Hot deals -------------------------------------------------
            offers.maybeWhen(
              data: (deals) => deals.isEmpty
                  ? const SizedBox.shrink()
                  : Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const SectionHeader(title: '🔥 Hot deals near you'),
                        SizedBox(
                          height: 148,
                          child: ListView.separated(
                            scrollDirection: Axis.horizontal,
                            padding:
                                const EdgeInsets.symmetric(horizontal: 20),
                            itemCount: deals.length,
                            separatorBuilder: (_, __) =>
                                const SizedBox(width: 12),
                            itemBuilder: (context, index) => OfferCard(
                              offer: deals[index],
                              onTap: () => context.push(
                                RouteNames.salonDetail(deals[index].salonId),
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
              orElse: () => const SizedBox.shrink(),
            ),

            // --- Nearby salons ---------------------------------------------
            const SectionHeader(title: 'Salons near you'),
            AsyncValueView(
              value: salons,
              onRetry: () => ref.invalidate(nearbySalonsProvider),
              data: (items) => items.isEmpty
                  ? const EmptyState(
                      icon: Icons.search_off_rounded,
                      title: 'No salons match your filters',
                      message: 'Try widening the price range or rating.',
                    )
                  : Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 20),
                      child: Column(
                        children: [
                          for (final item in items) ...[
                            SalonCard(
                              salon: item.salon,
                              distanceKm: item.distanceKm,
                              onTap: () => context.push(
                                RouteNames.salonDetail(item.salon.id),
                              ),
                            ),
                            const SizedBox(height: 14),
                          ],
                        ],
                      ),
                    ),
            ),
            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }
}
