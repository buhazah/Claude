import 'package:intl/intl.dart';

import '../constants/app_constants.dart';

/// Formatting helpers shared across features. Keep locale-aware formatting
/// here so screens never hand-roll date/price strings.
abstract final class Formatters {
  static final NumberFormat _price = NumberFormat('#,##0.##');
  static final DateFormat _day = DateFormat('EEE, d MMM');
  static final DateFormat _time = DateFormat('h:mm a');
  static final DateFormat _dayTime = DateFormat('EEE, d MMM · h:mm a');

  static String price(double amount) =>
      '${AppConstants.currencySymbol} ${_price.format(amount)}';

  static String day(DateTime date) => _day.format(date);

  static String time(DateTime date) => _time.format(date);

  static String dayTime(DateTime date) => _dayTime.format(date);

  static String duration(int minutes) {
    if (minutes < 60) return '$minutes min';
    final h = minutes ~/ 60;
    final m = minutes % 60;
    return m == 0 ? '${h}h' : '${h}h ${m}m';
  }
}
