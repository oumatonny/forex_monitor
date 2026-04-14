
// lib/widgets/connection_button.dart
import 'package:flutter/material.dart';
import '../providers/trading_provider.dart';

class ConnectionButton extends StatelessWidget {
  final TradingProvider provider;
  
  const ConnectionButton({super.key, required this.provider});
  
  @override
  Widget build(BuildContext context) {
    return IconButton(
      icon: Icon(
        provider.isConnected ? Icons.bluetooth_connected : Icons.bluetooth_disabled,
        color: provider.isConnected ? Colors.green : Colors.red,
      ),
      onPressed: () async {
        if (provider.isConnected) {
          provider.disconnect();
        } else {
          final success = await provider.connectToMT5();
          if (success) {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('Connected to MT5!')),
            );
          } else {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('Failed to connect to MT5')),
            );
          }
        }
      },
    );
  }
}