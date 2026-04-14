// lib/main.dart
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'providers/trading_provider.dart';
import 'screens/dashboard_screen.dart';
import 'screens/signal_screen.dart';
import 'screens/history_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  
  // Initialize notifications
  const AndroidInitializationSettings androidSettings =
      AndroidInitializationSettings('@mipmap/ic_launcher');
  const InitializationSettings settings = InitializationSettings(
    android: androidSettings,
  );
  await FlutterLocalNotificationsPlugin().initialize(settings);
  
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => TradingProvider()),
      ],
      child: MaterialApp(
        title: 'SMC Trading App',
        theme: ThemeData(
          brightness: Brightness.dark,
          primarySwatch: Colors.blue,
          scaffoldBackgroundColor: const Color(0xFF0E1A2B),
          appBarTheme: const AppBarTheme(
            backgroundColor: Color(0xFF1A2A3A),
            foregroundColor: Colors.white,
            elevation: 0,
          ),
          cardTheme: CardTheme(
            color: const Color(0xFF1A2A3A),
            elevation: 2,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
          ),
        ),
        home: const DashboardScreen(),
        routes: {
          '/signals': (context) => const SignalScreen(),
          '/history': (context) => const HistoryScreen(),
        },
        debugShowCheckedModeBanner: false,
      ),
    );
  }
}