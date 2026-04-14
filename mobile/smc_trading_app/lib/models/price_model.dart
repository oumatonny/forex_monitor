// lib/models/price_model.dart
class PriceData {
  final double bid;
  final double ask;
  final double spread;
  final int volume;
  final DateTime timestamp;
  
  PriceData({
    required this.bid,
    required this.ask,
    required this.spread,
    required this.volume,
    required this.timestamp,
  });
  
  double get mid => (bid + ask) / 2;
}