import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/errors/error_text.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/formatters.dart';
import '../../../../core/widgets/section_header.dart';
import '../../../businesses/domain/entities/business.dart';
import '../../../businesses/domain/entities/working_hours.dart';
import '../../../businesses/presentation/providers/business_providers.dart';
import '../providers/owner_providers.dart';

/// Availability management: weekly working hours, bookable capacity
/// (chairs / rooms / staff), and one-off blocked slots.
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
    final business = ref.watch(ownerBusinessProvider).valueOrNull;
    if (business == null) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    final blocked = ref.watch(blockedSlotsProvider(business.id));
    final resources = ref.watch(businessResourcesProvider(business.id));

    return Scaffold(
      appBar: AppBar(title: const Text('Availability')),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _showBlockSlotFlow(context, ref, business),
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
                      business: business,
                      weekday: weekday,
                      name: _weekdayNames[weekday]!,
                    ),
                ],
              ),
            ),
          ),
          const SectionHeader(title: 'Bookable capacity'),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            child: Card(
              child: Column(
                children: [
                  const Padding(
                    padding: EdgeInsets.fromLTRB(16, 14, 16, 4),
                    child: Text(
                      'Chairs, rooms or staff that can serve customers at '
                      'the same time. With none listed, you take one '
                      'booking per slot.',
                      style: TextStyle(
                          color: AppColors.textSecondary, fontSize: 13),
                    ),
                  ),
                  resources.when(
                    loading: () => const Padding(
                      padding: EdgeInsets.all(16),
                      child: Center(child: CircularProgressIndicator()),
                    ),
                    error: (error, _) => Padding(
                      padding: const EdgeInsets.all(16),
                      child: Text(errorText(error)),
                    ),
                    data: (items) => Column(
                      children: [
                        for (final resource in items)
                          ListTile(
                            leading: const Icon(Icons.chair_alt_outlined),
                            title: Text(resource.name),
                            trailing: IconButton(
                              icon: const Icon(Icons.close_rounded),
                              onPressed: () => ref
                                  .read(ownerActionsProvider)
                                  .removeResource(business.id, resource.id),
                            ),
                          ),
                        ListTile(
                          leading: const Icon(Icons.add_rounded,
                              color: AppColors.primary),
                          title: const Text(
                            'Add capacity unit',
                            style: TextStyle(color: AppColors.primary),
                          ),
                          onTap: () => _addResource(context, ref, business),
                        ),
                      ],
                    ),
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
              error: (error, _) => Text(errorText(error)),
              data: (slots) {
                if (slots.isEmpty) {
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
                    for (final slot in slots)
                      Card(
                        child: ListTile(
                          leading: const Icon(Icons.block_rounded,
                              color: AppColors.danger),
                          title: Text(
                            '${Formatters.dayTime(slot.start)} → '
                            '${Formatters.time(slot.end)}',
                          ),
                          trailing: IconButton(
                            icon: const Icon(Icons.close_rounded),
                            onPressed: () => ref
                                .read(ownerActionsProvider)
                                .unblockSlot(business.id, slot.id),
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

  Future<void> _addResource(
    BuildContext context,
    WidgetRef ref,
    Business business,
  ) async {
    final controller = TextEditingController();
    final name = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Add capacity unit'),
        content: TextField(
          controller: controller,
          autofocus: true,
          textCapitalization: TextCapitalization.words,
          decoration: const InputDecoration(
            hintText: 'e.g. Chair 2, Room B, Sara',
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () =>
                Navigator.of(context).pop(controller.text.trim()),
            child: const Text('Add'),
          ),
        ],
      ),
    );
    if (name != null && name.isNotEmpty) {
      await ref.read(ownerActionsProvider).addResource(business.id, name);
    }
  }

  Future<void> _showBlockSlotFlow(
    BuildContext context,
    WidgetRef ref,
    Business business,
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
    await ref.read(ownerActionsProvider).blockSlot(business.id, start, end);
  }
}

/// One weekday row: closed toggle + open/close time pickers.
class _DayHoursTile extends ConsumerWidget {
  const _DayHoursTile({
    required this.business,
    required this.weekday,
    required this.name,
  });

  final Business business;
  final int weekday;
  final String name;

  Future<void> _editHours(BuildContext context, WidgetRef ref) async {
    final hours = business.workingHours.forWeekday(weekday);
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
          business.id,
          business.workingHours.updating(
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
    final hours = business.workingHours.forWeekday(weekday);
    return ListTile(
      title: Text(name, style: const TextStyle(fontWeight: FontWeight.w600)),
      subtitle: Text(
        hours.closed
            ? 'Closed'
            : '${Formatters.minutesOfDay(hours.openMinutes)} – '
                '${Formatters.minutesOfDay(hours.closeMinutes)}',
        style: TextStyle(
          color: hours.closed ? AppColors.danger : AppColors.textSecondary,
        ),
      ),
      trailing: Switch(
        value: !hours.closed,
        onChanged: (isOpen) {
          ref.read(ownerActionsProvider).updateWorkingHours(
                business.id,
                business.workingHours.updating(
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
