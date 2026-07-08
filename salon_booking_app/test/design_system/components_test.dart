import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:salon_booking_app/core/design_system/design_system.dart';

Widget _wrap(Widget child) => MaterialApp(
      theme: AppTheme.light(),
      home: Scaffold(body: Center(child: child)),
    );

void main() {
  group('AppButton', () {
    testWidgets('fires onPressed and shows label', (tester) async {
      var taps = 0;
      await tester.pumpWidget(_wrap(
        AppButton(label: 'Book now', onPressed: () => taps++),
      ));
      expect(find.text('Book now'), findsOneWidget);
      await tester.tap(find.byType(AppButton));
      expect(taps, 1);
    });

    testWidgets('loading shows spinner and blocks taps', (tester) async {
      var taps = 0;
      await tester.pumpWidget(_wrap(
        AppButton(label: 'Book', onPressed: () => taps++, loading: true),
      ));
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(find.text('Book'), findsNothing);
      await tester.tap(find.byType(AppButton), warnIfMissed: false);
      expect(taps, 0);
      // Spinner animates forever; settle a fixed frame instead.
      await tester.pump(const Duration(milliseconds: 50));
    });

    testWidgets('renders all variants', (tester) async {
      await tester.pumpWidget(_wrap(Column(
        children: [
          for (final variant in AppButtonVariant.values)
            AppButton(
              label: variant.name,
              onPressed: () {},
              variant: variant,
              size: AppButtonSize.small,
            ),
        ],
      )));
      for (final variant in AppButtonVariant.values) {
        expect(find.text(variant.name), findsOneWidget);
      }
    });
  });

  testWidgets('AppRatingBadge shows one-decimal score and count',
      (tester) async {
    await tester.pumpWidget(_wrap(
      const AppRatingBadge(rating: 4.0, count: 12),
    ));
    expect(find.text('4.0'), findsOneWidget);
    expect(find.text('(12)'), findsOneWidget);
  });

  testWidgets('AppFilterChip toggles through onSelected', (tester) async {
    bool? received;
    await tester.pumpWidget(_wrap(
      AppFilterChip(
        label: 'Spa',
        selected: false,
        onSelected: (value) => received = value,
      ),
    ));
    await tester.tap(find.text('Spa'));
    expect(received, isTrue);
  });

  testWidgets('AppSearchBar reports changes and clears', (tester) async {
    final changes = <String>[];
    await tester.pumpWidget(_wrap(
      AppSearchBar(hint: 'Search salons', onChanged: changes.add),
    ));
    await tester.enterText(find.byType(TextField), 'nails');
    await tester.pump();
    expect(changes, contains('nails'));
    await tester.tap(find.byIcon(Icons.close_rounded));
    await tester.pump();
    expect(changes.last, '');
  });

  testWidgets('AppBookingTimeline renders every step', (tester) async {
    await tester.pumpWidget(_wrap(
      const AppBookingTimeline(steps: [
        AppTimelineStep(
          title: 'Requested',
          subtitle: 'Today, 2:15 PM',
          state: AppTimelineState.complete,
        ),
        AppTimelineStep(title: 'Confirmed', state: AppTimelineState.active),
        AppTimelineStep(title: 'Completed'),
      ]),
    ));
    expect(find.text('Requested'), findsOneWidget);
    expect(find.text('Confirmed'), findsOneWidget);
    expect(find.text('Completed'), findsOneWidget);
    expect(find.byIcon(Icons.check_rounded), findsOneWidget);
  });

  testWidgets('AppEmptyState fires its action', (tester) async {
    var actions = 0;
    await tester.pumpWidget(_wrap(
      AppEmptyState(
        icon: Icons.event_note_outlined,
        title: 'No bookings yet',
        message: 'Book your first appointment.',
        actionLabel: 'Discover',
        onAction: () => actions++,
      ),
    ));
    expect(find.text('No bookings yet'), findsOneWidget);
    await tester.tap(find.text('Discover'));
    expect(actions, 1);
  });

  testWidgets('AppErrorState retries', (tester) async {
    var retries = 0;
    await tester.pumpWidget(_wrap(
      AppErrorState(message: 'Check your connection.', onRetry: () => retries++),
    ));
    expect(find.text('Something went wrong'), findsOneWidget);
    await tester.tap(find.text('Retry'));
    expect(retries, 1);
  });

  testWidgets('AppServiceCard shows price, struck original and action',
      (tester) async {
    var booked = 0;
    await tester.pumpWidget(_wrap(
      AppServiceCard(
        name: 'Haircut & styling',
        priceLabel: 'AED 90',
        originalPriceLabel: 'AED 130',
        durationLabel: '45 min',
        actionLabel: 'Book',
        onAction: () => booked++,
      ),
    ));
    expect(find.text('AED 90'), findsOneWidget);
    expect(find.text('AED 130'), findsOneWidget);
    await tester.tap(find.text('Book'));
    expect(booked, 1);
  });

  testWidgets('AppOfferCard shows discount and opens on tap', (tester) async {
    var opened = 0;
    await tester.pumpWidget(_wrap(
      AppOfferCard(
        discountLabel: '-30%',
        title: 'Afternoon happy hour',
        subtitle: 'Glow Lounge',
        untilLabel: 'until 6:00 PM',
        onTap: () => opened++,
      ),
    ));
    expect(find.text('-30%'), findsOneWidget);
    await tester.tap(find.text('Afternoon happy hour'));
    expect(opened, 1);
  });

  testWidgets('AppBusinessCard renders facts without an image',
      (tester) async {
    await tester.pumpWidget(_wrap(
      AppBusinessCard(
        name: 'Glow Lounge',
        rating: 4.8,
        ratingCount: 214,
        tag: 'Women',
        distanceLabel: '0.8 km',
        priceLabel: 'from AED 90',
        badge: '-30%',
        onTap: () {},
      ),
    ));
    expect(find.text('Glow Lounge'), findsOneWidget);
    expect(find.text('4.8'), findsOneWidget);
    expect(find.text('from AED 90'), findsOneWidget);
    expect(find.text('-30%'), findsOneWidget);
  });

  testWidgets('AppSkeletonList pulses without errors', (tester) async {
    await tester.pumpWidget(_wrap(
      const SingleChildScrollView(child: AppSkeletonList(count: 2)),
    ));
    expect(find.byType(AppSkeletonCard), findsNWidgets(2));
    await tester.pump(AppMotion.skeletonPulse);
    await tester.pump(AppMotion.skeletonPulse);
  });
}
