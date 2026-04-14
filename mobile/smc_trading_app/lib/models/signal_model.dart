// lib/models/signal_model.dart
class TradingSignal {
  final String type; // BUY, SELL, NEUTRAL
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
  bool? tp1Hit;
  bool? tp2Hit;
  bool? tp3Hit;
  bool? slHit;
  
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
    this.tp1Hit,
    this.tp2Hit,
    this.tp3Hit,
    this.slHit,
  });
  
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
  
  factory TradingSignal.fromJson(Map<String, dynamic> json) {
    return TradingSignal(
      type: json['type'],
      confidence: json['confidence'],
      entry: json['entry'],
      tp1: json['tp1'],
      tp2: json['tp2'],
      tp3: json['tp3'],
      sl: json['sl'],
      expectedMove: json['expectedMove'],
      generatedAt: DateTime.parse(json['generatedAt']),
      validUntil: DateTime.parse(json['validUntil']),
      isActive: json['isActive'],
      tp1Hit: json['tp1Hit'],
      tp2Hit: json['tp2Hit'],
      tp3Hit: json['tp3Hit'],
      slHit: json['slHit'],
    );
  }
}

