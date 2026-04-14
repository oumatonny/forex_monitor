// lib/services/background_service.dart
import 'package:workmanager/workmanager.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'notification_service.dart';
import '../models/signal_model.dart';

class BackgroundService {
  static void callbackDispatcher() {
    Workmanager().executeTask((task, inputData) async {
      switch (task) {
        case "generateSignal":
          await generateAndStoreSignal();
          break;
        case "monitorPrices":
          await monitorPriceLevels();
          break;
      }
      return Future.value(true);
    });
  }
  
  static Future<void> generateAndStoreSignal() async {
    try {
      final response = await http.get(
        Uri.parse('http://127.0.0.1:51908/api/signal/EURUSD'),
      );
      
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        final signal = TradingSignal.fromJson(data);
        
        // Store signal locally
        await storeSignal(signal);
        
        // Send notification
        await NotificationService.showNewSignalNotification(
          signal.type,
          signal.confidence,
        );
      }
    } catch (e) {
      print('Error generating signal: $e');
    }
  }
  
  static Future<void> monitorPriceLevels() async {
    try {
      final response = await http.get(
        Uri.parse('http://127.0.0.1:51908/api/price/EURUSD'),
      );
      
      if (response.statusCode == 200) {
        final priceData = json.decode(response.body);
        final currentPrice = priceData['bid'];
        
        // Get active signal
        final activeSignal = await getActiveSignal();
        
        if (activeSignal != null && activeSignal.isActive) {
          // Check TP levels
          if (activeSignal.type == 'BUY') {
            if (!activeSignal.tp1Hit && currentPrice >= activeSignal.tp1) {
              activeSignal.tp1Hit = true;
              await NotificationService.showTPHitNotification(
                ((activeSignal.tp1 - activeSignal.entry) / activeSignal.entry * 100)
              );
            }
            
            if (!activeSignal.slHit && currentPrice <= activeSignal.sl) {
              activeSignal.slHit = true;
              activeSignal.isActive = false;
              await NotificationService.showSLHitNotification(
                ((activeSignal.entry - activeSignal.sl) / activeSignal.entry * 100)
              );
            }
          }
          
          await updateSignal(activeSignal);
        }
      }
    } catch (e) {
      print('Error monitoring prices: $e');
    }
  }
  
  static Future<void> storeSignal(TradingSignal signal) async {
    // Implement local storage using Hive or SharedPreferences
  }
  
  static Future<TradingSignal?> getActiveSignal() async {
    // Retrieve active signal from local storage
    return null;
  }
  
  static Future<void> updateSignal(TradingSignal signal) async {
    // Update signal in local storage
  }
}