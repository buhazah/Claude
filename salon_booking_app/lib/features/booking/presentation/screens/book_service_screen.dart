import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/constants/app_constants.dart';
import '../../../../core/errors/error_text.dart';
import '../../../../core/router/route_names.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/formatters.dart';
import '../../../../core/widgets/empty_state.dart';
import '../../../../core/widgets/primary_button.dart';
import '../../../businesses/domain/entities/service_offering.dart';
import '../../../businesses/presentation/providers/business_providers.dart';
import '../../../offers/domain/services/offer_pricing.dart';
import '../../../offers/presentation/providers/offer_providers.dart';
import '../controllers/booking_flow_controller.dart';
import '../providers/booking_providers.dart';

/// Taps 2 and 3 of the booking flow: pick a slot, confirm.
/// (Tap 1 was "Book" on a service in the business detail screen.)
class BookServiceScreen extends ConsumerStatefulWidget {
  const BookServiceScreen({
    super.key,
    required this.businessId,
    required this.serviceId,
  });

  final String businessId;
  final String serviceId;

  @override
  ConsumerState<BookServiceScreen> createState() => _BookServiceScreenState();
}

class _BookServiceScreenState extends ConsumerState<BookServiceScreen> {
  late DateTime _selectedDay;

  @override
  void initState() {
    super.initState();
    final now = DateTime.now();
    _selectedDay = DateTime(now.year, now.month, now.day);
  }

  @override
  Widget build(BuildContext context) {
    final business = ref.watch(businessProvider(widget.businessId)).valueOrNull;
    final services =
        ref.watch(businessServicesProvider(widget.businessId)).valueOrNull;
    final flow = ref.watch(bookingFlowControllerProvider);

    ref.listen(bookingFlowControllerProvider, (previous, next) {
      final error = next.error;
      if (error != null && error != previous?.error) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(error)));
      }
    });

    // Booked! Show the confirmation view instead of the picker.
    if (flow.confirmedBookingId != null) {
      return _ConfirmationView(businessName: business?.name ?? '');
    }

    if (business == null || services == null) {
      return const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      );
    }

    ServiceOffering? service;
    for (final s in services) {
      if (s.id == widget.serviceId) service = s;
    }
    if (service == null) {
      return const Scaffold(
        body: EmptyState(
          icon: Icons.design_services_outlined,
          title: 'Service no longer available',
        ),
      );
    }

    final offers = ref.watch(businessOffersProvider(business.id)).valueOrNull;
    final liveOffer =
        OfferPricing.bestLiveOffer(offers ?? const [], business.id);
    final price = liveOffer == null
        ? service.price
        : OfferPricing.discountedPrice(service.price, liveOffer);

    final slots = ref.watch(availableSlotsProvider((
      businessId: business.id,
      durationMinutes: service.durationMinutes,
      day: _selectedDay,
    )));

    return Scaffold(
      appBar: AppBar(title: Text(business.name)),
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // --- Service summary ---
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 8, 20, 0),
            child: Card(
              child: ListTile(
                title: Text(service.name,
                    style: const TextStyle(fontWeight: FontWeight.w700)),
                subtitle:
                    Text(Formatters.duration(service.durationMinutes)),
                trailing: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(
                      Formatters.price(price),
                      style: const TextStyle(
                        color: AppColors.primary,
                        fontWeight: FontWeight.w800,
                        fontSize: 16,
                      ),
                    ),
                    if (liveOffer != null)
                      Text(
                        '${liveOffer.discountPercent}% off applied',
                        style: const TextStyle(
                          color: AppColors.success,
                          fontSize: 12,
                        ),
                      ),
                  ],
                ),
              ),
            ),
          ),

          // --- Day picker ---
          SizedBox(
            height: 88,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.all(20),
              itemCount: AppConstants.bookingHorizonDays,
              separatorBuilder: (_, __) => const SizedBox(width: 8),
              itemBuilder: (context, index) {
                final day = DateTime.now().add(Duration(days: index));
                final normalized = DateTime(day.year, day.month, day.day);
                final selected = normalized == _selectedDay;
                return ChoiceChip(
                  label: Text(index == 0 ? 'Today' : Formatters.day(day)),
                  selected: selected,
                  onSelected: (_) {
                    setState(() => _selectedDay = normalized);
                    ref
                        .read(bookingFlowControllerProvider.notifier)
                        .clearSlot();
                  },
                );
              },
            ),
          ),

          // --- Slot grid (tap 2) ---
          Expanded(
            child: slots.when(
              loading: () =>
                  const Center(child: CircularProgressIndicator()),
              error: (error, _) => EmptyState(
                icon: Icons.wifi_off_rounded,
                title: 'Could not load availability',
                message: errorText(error),
              ),
              data: (available) => available.isEmpty
                  ? const EmptyState(
                      icon: Icons.event_busy_rounded,
                      title: 'No free slots this day',
                      message: 'Try another day.',
                    )
                  : GridView.builder(
                      padding: const EdgeInsets.symmetric(horizontal: 20),
                      gridDelegate:
                          const SliverGridDelegateWithFixedCrossAxisCount(
                        crossAxisCount: 3,
                        mainAxisSpacing: 10,
                        crossAxisSpacing: 10,
                        childAspectRatio: 2.4,
                      ),
                      itemCount: available.length,
                      itemBuilder: (context, index) {
                        final slot = available[index];
                        final selected = flow.slot == slot;
                        return ChoiceChip(
                          label: Text(Formatters.time(slot.start)),
                          selected: selected,
                          labelStyle: TextStyle(
                            color: selected
                                ? AppColors.primaryDark
                                : AppColors.textPrimary,
                            fontWeight: FontWeight.w600,
                          ),
                          onSelected: (_) => ref
                              .read(bookingFlowControllerProvider.notifier)
                              .selectSlot(slot),
                        );
                      },
                    ),
            ),
          ),
        ],
      ),

      // --- Confirm bar (tap 3) ---
      bottomNavigationBar: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: PrimaryButton(
            label: flow.slot == null
                ? 'Pick a time slot'
                : 'Confirm · ${Formatters.dayTime(flow.slot!.start)}',
            loading: flow.submitting,
            onPressed: flow.slot == null
                ? null
                : () => ref
                    .read(bookingFlowControllerProvider.notifier)
                    .confirm(business: business, service: service!),
          ),
        ),
      ),
    );
  }
}

class _ConfirmationView extends StatelessWidget {
  const _ConfirmationView({required this.businessName});

  final String businessName;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Icon(Icons.check_circle_rounded,
                  size: 96, color: AppColors.success),
              const SizedBox(height: 24),
              Text(
                'Booking requested!',
                textAlign: TextAlign.center,
                style: Theme.of(context)
                    .textTheme
                    .headlineSmall
                    ?.copyWith(fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 8),
              Text(
                '$businessName will confirm your appointment shortly. '
                'Track it in My Bookings.',
                textAlign: TextAlign.center,
                style: const TextStyle(color: AppColors.textSecondary),
              ),
              const SizedBox(height: 40),
              PrimaryButton(
                label: 'View my bookings',
                onPressed: () => context.go(RouteNames.myBookings),
              ),
              TextButton(
                onPressed: () => context.go(RouteNames.home),
                child: const Text('Back to home'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
