import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/formatters.dart';
import '../../../../core/widgets/section_header.dart';
import '../../../salons/domain/entities/salon.dart';
import '../../../salons/domain/entities/working_hours.dart';
import '../../../salons/presentation/providers/salon_providers.dart';
import '../providers/owner_providers.dart';

/// Availability management: weekly working hours + one-off blocked slots.
class AvailabilityScreen extends ConsumerWidget {
  const AvailabilityScreen({super.key});

  static const _weekdayNames = {
    DateTime.monday: 'Monday',
    DateTime.tuesday: 'Tuesday',
    DateTime.wednesday: 'Wednesday',
    DateTime.thursday: 'Thursday',
    DateTime.friday: 'Friday',
    DateTime.saturday: 'Saturday',
    DateTime.sunday: 'Sunday',
  };

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final salon = ref.watch(ownerSalonProvider).valueOrNull;
    if (salon == null) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    final blocked = ref.watch(blockedSlotsProvider(salon.id));

    return Scaffold(
      appBar: AppBar(title: const Text('Availability')),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _showBlockSlotSheet(context, ref, salon),
        icon: const Icon(Icons.block_rounded),
        label: const Text('Block time'),
      ),
      body: ListView(
        padding: const EdgeInsets.only(bottom: 96),
        children: [
          const SectionHeader(title: 'Working hours'),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            child: Card(
              child: Column(
                children: [
                  for (final weekday in _weekdayNames.keys)
                    _DayHoursTile(
                      salon: salon,
                      weekday: weekday,
                      name: _weekdayNames[weekday]!,
                    ),
                ],
              ),
            ),
          ),
          const SectionHeader(title: 'Blocked slots'),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            child: blocked.when(
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (error, _) => Text(error.toString()),
              data: (slots) {
                final upcoming = slots
                    .where((s) => s.end.isAfter(DateTime.now()))
                    .toList();
                if (upcoming.isEmpty) {
                  return const Card(
                    child: Padding(
                      padding: EdgeInsets.all(20),
                      child: Text(
                        'No blocked slots. Block time for breaks, '
                        'walk-ins or maintenance.',
                        style: TextStyle(color: AppColors.textSecondary),
                      ),
                    ),
                  );
                }
                return Column(
                  children: [
                    for (final slot in upcoming)
                      Card(
                        child: ListTile(
                          leading: const Icon(Icons.block_rounded,
                              color: AppColors.danger),
                          title: Text(
                            '${Formatters.dayTime(slot.start)} → '
                            '${Formatters.time(slot.end)}',
                          ),
                          subtitle: slot.reason.isEmpty
                              ? null
                              : Text(slot.reason),
                          trailing: IconButton(
                            icon: const Icon(Icons.close_rounded),
                            onPressed: () => ref
                                .read(ownerActionsProvider)
                                .unblockSlot(salon.id, slot.id),
                          ),
                        ),
                      ),
                  ],
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _showBlockSlotSheet(
    BuildContext context,
    WidgetRef ref,
    Salon salon,
  ) async {
    final now = DateTime.now();
    var start = DateTime(now.year, now.month, now.day, now.hour + 1);
    var end = start.add(const Duration(hours: 1));

    final date = await showDatePicker(
      context: context,
      initialDate: now,
      firstDate: now,
      lastDate: now.add(const Duration(days: 60)),
    );
    if (date == null || !context.mounted) return;

    final startTime = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.fromDateTime(start),
      helpText: 'Block from',
    );
    if (startTime == null || !context.mounted) return;

    final endTime = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.fromDateTime(end),
      helpText: 'Block until',
    );
    if (endTime == null || !context.mounted) return;

    start = DateTime(
        date.year, date.month, date.day, startTime.hour, startTime.minute);
    end = DateTime(
        date.year, date.month, date.day, endTime.hour, endTime.minute);
    if (!end.isAfter(start)) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('End must be after start')),
      );
      return;
    }
    await ref
        .read(ownerActionsProvider)
        .blockSlot(salon.id, start, end, 'Blocked by owner');
  }
}

/// One weekday row: closed toggle + open/close time pickers.
class _DayHoursTile extends ConsumerWidget {
  const _DayHoursTile({
    required this.salon,
    required this.weekday,
    required this.name,
  });

  final Salon salon;
  final int weekday;
  final String name;

  String _format(int minutes) {
    final h = minutes ~/ 60;
    final m = minutes % 60;
    final period = h >= 12 ? 'PM' : 'AM';
    final hour12 = h % 12 == 0 ? 12 : h % 12;
    return '$hour12:${m.toString().padLeft(2, '0')} $period';
  }

  Future<void> _editHours(BuildContext context, WidgetRef ref) async {
    final hours = salon.workingHours.forWeekday(weekday);
    final open = await showTimePicker(
      context: context,
      initialTime: TimeOfDay(
          hour: hours.openMinutes ~/ 60, minute: hours.openMinutes % 60),
      helpText: '$name — opens at',
    );
    if (open == null || !context.mounted) return;
    final close = await showTimePicker(
      context: context,
      initialTime: TimeOfDay(
          hour: hours.closeMinutes ~/ 60, minute: hours.closeMinutes % 60),
      helpText: '$name — closes at',
    );
    if (close == null || !context.mounted) return;

    final openMinutes = open.hour * 60 + open.minute;
    final closeMinutes = close.hour * 60 + close.minute;
    if (closeMinutes <= openMinutes) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Closing time must be after opening')),
      );
      return;
    }
    await ref.read(ownerActionsProvider).updateWorkingHours(
          salon.id,
          salon.workingHours.updating(
            weekday,
            DayHours(
              closed: false,
              openMinutes: openMinutes,
              closeMinutes: closeMinutes,
            ),
          ),
        );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final hours = salon.workingHours.forWeekday(weekday);
    return ListTile(
      title: Text(name, style: const TextStyle(fontWeight: FontWeight.w600)),
      subtitle: Text(
        hours.closed
            ? 'Closed'
            : '${_format(hours.openMinutes)} – ${_format(hours.closeMinutes)}',
        style: TextStyle(
          color:
              hours.closed ? AppColors.danger : AppColors.textSecondary,
        ),
      ),
      trailing: Switch(
        value: !hours.closed,
        onChanged: (isOpen) {
          ref.read(ownerActionsProvider).updateWorkingHours(
                salon.id,
                salon.workingHours.updating(
                  weekday,
                  isOpen
                      ? const DayHours.standard()
                      : const DayHours.dayOff(),
                ),
              );
        },
      ),
      onTap: hours.closed ? null : () => _editHours(context, ref),
    );
  }
}
