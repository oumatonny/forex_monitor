// lib/providers/trading_provider.dart
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'dart:async';
import '../models/trading_models.dart';

class TradingProvider extends ChangeNotifier {
  // API Configuration (Replace with your server IP)
  static const String baseUrl = 'http://127.0.0.1:51908';
  
  PriceData? _currentPrice;
  TradingSignal? _currentSignal;
  List<TradingSignal> _signalHistory = [];
  bool _isConnected = false;
  Timer? _priceTimer;
  Timer? _signalTimer;
  
  PriceData? get currentPrice => _currentPrice;
  TradingSignal? get currentSignal => _currentSignal;
  List<TradingSignal> get signalHistory => _signalHistory;
  bool get isConnected => _isConnected;
  
  TradingProvider() {
    _loadSignalHistory();
    _startAutoRefresh();
  }
  
  Future<bool> connectToMT5() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/api/connect'),
        headers: {'Content-Type': 'application/json'},
      ).timeout(const Duration(seconds: 5));
      
      if (response.statusCode == 200) {
        _isConnected = true;
        await _fetchCurrentPrice();
        await _generateSignal();
        _startPriceStream();
        _startSignalGeneration();
        notifyListeners();
        return true;
      }
    } catch (e) {
      print('Connection error: $e');
    }
    return false;
  }
  
  void disconnect() {
    _isConnected = false;
    _priceTimer?.cancel();
    _signalTimer?.cancel();
    notifyListeners();
  }
  
  void _startPriceStream() {
    _priceTimer = Timer.periodic(const Duration(seconds: 2), (timer) {
      if (_isConnected) {
        _fetchCurrentPrice();
      }
    });
  }
  
  void _startSignalGeneration() {
    _signalTimer = Timer.periodic(const Duration(minutes: 20), (timer) {
      if (_isConnected) {
        _generateSignal();
      }
    });
  }
  
  void _startAutoRefresh() {
    Timer.periodic(const Duration(seconds: 1), (timer) {
      if (_currentSignal != null && _isConnected) {
        _checkTPSLHits();
        notifyListeners();
      }
    });
  }
  
  Future<void> _fetchCurrentPrice() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/api/price/EURUSD'),
      ).timeout(const Duration(seconds: 2));
      
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        _currentPrice = PriceData.fromJson(data);
        notifyListeners();
      }
    } catch (e) {
      // Use simulated data if API fails
      _generateSimulatedPrice();
    }
  }
  
  void _generateSimulatedPrice() {
    final basePrice = _currentSignal?.entry ?? 1.08950;
    final randomMove = (DateTime.now().millisecondsSinceEpoch % 1000) / 1000000;
    _currentPrice = PriceData(
      bid: basePrice + randomMove,
      ask: basePrice + randomMove + 0.0001,
      spread: 0.0001,
      volume: 1000 + (DateTime.now().millisecondsSinceEpoch % 5000).toInt(),
      timestamp: DateTime.now(),
    );
    notifyListeners();
  }
  
  Future<void> _generateSignal() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/api/signal/EURUSD'),
      ).timeout(const Duration(seconds: 5));
      
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        _currentSignal = TradingSignal.fromJson(data);
        _signalHistory.insert(0, _currentSignal!);
        if (_signalHistory.length > 20) _signalHistory.removeLast();
        await _saveSignalHistory();
        notifyListeners();
        
        // Show notification
        await _showNotification(
          'New ${_currentSignal!.type} Signal',
          'Confidence: ${_currentSignal!.confidence.toStringAsFixed(0)}%',
        );
      }
    } catch (e) {
      // Generate simulated signal
      _generateSimulatedSignal();
    }
  }
  
  void _generateSimulatedSignal() {
    final currentPrice = _currentPrice?.mid ?? 1.08950;
    final random = DateTime.now().millisecondsSinceEpoch % 100;
    
    String signalType;
    double confidence;
    
    if (random < 40) {
      signalType = 'BUY';
      confidence = 65 + (random % 25);
    } else if (random < 80) {
      signalType = 'SELL';
      confidence = 65 + (random % 25);
    } else {
      signalType = 'NEUTRAL';
      confidence = 0;
    }
    
    const expectedMove = 0.0015;
    
    _currentSignal = TradingSignal(
      type: signalType,
      confidence: confidence,
      entry: currentPrice,
      tp1: signalType == 'BUY' ? currentPrice + (expectedMove * 0.6) : currentPrice - (expectedMove * 0.6),
      tp2: signalType == 'BUY' ? currentPrice + expectedMove : currentPrice - expectedMove,
      tp3: signalType == 'BUY' ? currentPrice + (expectedMove * 1.4) : currentPrice - (expectedMove * 1.4),
      sl: signalType == 'BUY' ? currentPrice - (expectedMove * 0.5) : currentPrice + (expectedMove * 0.5),
      expectedMove: expectedMove,
      generatedAt: DateTime.now(),
      validUntil: DateTime.now().add(const Duration(minutes: 10)),
      isActive: true,
    );
    
    _signalHistory.insert(0, _currentSignal!);
    if (_signalHistory.length > 20) _signalHistory.removeLast();
    _saveSignalHistory();
    notifyListeners();
  }
  
  void _checkTPSLHits() {
    if (_currentSignal == null || !_currentSignal!.isActive) return;
    if (_currentPrice == null) return;
    
    final currentMid = _currentPrice!.mid;
    bool updated = false;
    
    if (_currentSignal!.type == 'BUY') {
      if (!_currentSignal!.tp1Hit && currentMid >= _currentSignal!.tp1) {
        _currentSignal!.tp1Hit = true;
        updated = true;
        _showNotification('🎯 TP1 HIT!', 'Profit achieved!');
      }
      if (!_currentSignal!.slHit && currentMid <= _currentSignal!.sl) {
        _currentSignal!.slHit = true;
        _currentSignal!.isActive = false;
        updated = true;
        _showNotification('🛑 STOP LOSS HIT', 'Position closed');
      }
    } else if (_currentSignal!.type == 'SELL') {
      if (!_currentSignal!.tp1Hit && currentMid <= _currentSignal!.tp1) {
        _currentSignal!.tp1Hit = true;
        updated = true;
        _showNotification('🎯 TP1 HIT!', 'Profit achieved!');
      }
      if (!_currentSignal!.slHit && currentMid >= _currentSignal!.sl) {
        _currentSignal!.slHit = true;
        _currentSignal!.isActive = false;
        updated = true;
        _showNotification('🛑 STOP LOSS HIT', 'Position closed');
      }
    }
    
    if (updated) {
      _saveSignalHistory();
      notifyListeners();
    }
  }
  
  Future<void> _showNotification(String title, String body) async {
    const AndroidNotificationDetails androidDetails = AndroidNotificationDetails(
      'trading_channel',
      'Trading Alerts',
      importance: Importance.high,
      priority: Priority.high,
    );
    const NotificationDetails details = NotificationDetails(android: androidDetails);
    await FlutterLocalNotificationsPlugin().show(
      DateTime.now().millisecondsSinceEpoch.remainder(100000),
      title,
      body,
      details,
    );
  }
  
  Future<void> _saveSignalHistory() async {
    final prefs = await SharedPreferences.getInstance();
    final List<String> signalsJson = _signalHistory.map((s) => jsonEncode(s.toJson())).toList();
    await prefs.setStringList('signal_history', signalsJson);
  }
  
  Future<void> _loadSignalHistory() async {
    final prefs = await SharedPreferences.getInstance();
    final signalsJson = prefs.getStringList('signal_history');
    if (signalsJson != null) {
      _signalHistory = signalsJson
          .map((s) => TradingSignal.fromJson(jsonDecode(s)))
          .toList();
      if (_signalHistory.isNotEmpty) {
        _currentSignal = _signalHistory.first;
      }
      notifyListeners();
    }
  }
  
  Duration get remainingValidity {
    if (_currentSignal == null) return Duration.zero;
    final remaining = _currentSignal!.validUntil.difference(DateTime.now());
    return remaining.isNegative ? Duration.zero : remaining;
  }
  
  @override
  void dispose() {
    _priceTimer?.cancel();
    _signalTimer?.cancel();
    super.dispose();
  }
}