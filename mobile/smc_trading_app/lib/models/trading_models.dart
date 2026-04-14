// lib/models/trading_models.dart
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
  
  factory PriceData.fromJson(Map<String, dynamic> json) {
    return PriceData(
      bid: json['bid'].toDouble(),
      ask: json['ask'].toDouble(),
      spread: json['spread'].toDouble(),
      volume: json['volume'],
      timestamp: DateTime.parse(json['timestamp']),
    );
  }
  
  Map<String, dynamic> toJson() => {
    'bid': bid,
    'ask': ask,
    'spread': spread,
    'volume': volume,
    'timestamp': timestamp.toIso8601String(),
  };
}

class TradingSignal {
  final String type;
  final double confidence;
  final double entry;
  final double tp1;
  final double tp2;
  final double tp3;
  final double sl;
  final double expectedMove;
  final DateTime generatedAt;
  final DateTime validUntil;
  bool isActive;
  bool tp1Hit;
  bool tp2Hit;
  bool tp3Hit;
  bool slHit;
  
  TradingSignal({
    required this.type,
    required this.confidence,
    required this.entry,
    required this.tp1,
    required this.tp2,
    required this.tp3,
    required this.sl,
    required this.expectedMove,
    required this.generatedAt,
    required this.validUntil,
    this.isActive = true,
    this.tp1Hit = false,
    this.tp2Hit = false,
    this.tp3Hit = false,
    this.slHit = false,
  });
  
  factory TradingSignal.fromJson(Map<String, dynamic> json) {
    return TradingSignal(
      type: json['type'],
      confidence: json['confidence'].toDouble(),
      entry: json['entry'].toDouble(),
      tp1: json['tp1'].toDouble(),
      tp2: json['tp2'].toDouble(),
      tp3: json['tp3'].toDouble(),
      sl: json['sl'].toDouble(),
      expectedMove: json['expectedMove'].toDouble(),
      generatedAt: DateTime.parse(json['generatedAt']),
      validUntil: DateTime.parse(json['validUntil']),
      isActive: json['isActive'] ?? true,
      tp1Hit: json['tp1Hit'] ?? false,
      tp2Hit: json['tp2Hit'] ?? false,
      tp3Hit: json['tp3Hit'] ?? false,
      slHit: json['slHit'] ?? false,
    );
  }
  
  Map<String, dynamic> toJson() => {
    'type': type,
    'confidence': confidence,
    'entry': entry,
    'tp1': tp1,
    'tp2': tp2,
    'tp3': tp3,
    'sl': sl,
    'expectedMove': expectedMove,
    'generatedAt': generatedAt.toIso8601String(),
    'validUntil': validUntil.toIso8601String(),
    'isActive': isActive,
    'tp1Hit': tp1Hit,
    'tp2Hit': tp2Hit,
    'tp3Hit': tp3Hit,
    'slHit': slHit,
  };
}