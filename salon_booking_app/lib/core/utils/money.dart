/// Money as an integer number of fils (1 AED = 100 fils).
///
/// Prices must never travel as `double`: floating point drift is untenable
/// once payments arrive. All arithmetic happens on integer fils; conversion
/// to AED doubles exists only at the UI edge (sliders, display).
class Money implements Comparable<Money> {
  const Money(this.fils) : assert(fils >= 0, 'Money cannot be negative');

  const Money.zero() : fils = 0;

  /// Parses user input in AED (e.g. "120" or "99.5"). Returns null when the
  /// input is not a valid non-negative amount.
  static Money? tryParseAed(String input) {
    final aed = double.tryParse(input.trim());
    if (aed == null || aed < 0) return null;
    return Money((aed * 100).round());
  }

  final int fils;

  double get aed => fils / 100;
  bool get isZero => fils == 0;

  Money operator +(Money other) => Money(fils + other.fils);

  /// Applies a percentage discount (0–100), rounding to the nearest fils.
  Money discountedBy(int percent) {
    final clamped = percent.clamp(0, 100);
    return Money(((fils * (100 - clamped)) / 100).round());
  }

  bool operator <(Money other) => fils < other.fils;
  bool operator >(Money other) => fils > other.fils;

  @override
  int compareTo(Money other) => fils.compareTo(other.fils);

  @override
  bool operator ==(Object other) => other is Money && other.fils == fils;

  @override
  int get hashCode => fils.hashCode;

  @override
  String toString() => 'Money(${aed.toStringAsFixed(2)} AED)';
}
