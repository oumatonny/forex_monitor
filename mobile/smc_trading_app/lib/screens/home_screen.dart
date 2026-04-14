// lib/screens/history_screen.dart
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/trading_provider.dart';

class HistoryScreen extends StatelessWidget {
  const HistoryScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Signal History'),
        centerTitle: true,
      ),
      body: Consumer<TradingProvider>(
        builder: (context, provider, child) {
          if (provider.signalHistory.isEmpty) {
            return const Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.history, size: 64, color: Colors.grey),
                  SizedBox(height: 16),
                  Text('No signals yet'),
                  SizedBox(height: 8),
                  Text('Connect to MT5 to start trading'),
                ],
              ),
            );
          }
          
          return ListView.builder(
            padding: const EdgeInsets.all(16),
            itemCount: provider.signalHistory.length,
            itemBuilder: (context, index) {
              final signal = provider.signalHistory[index];
              return _buildHistoryCard(signal);
            },
          );
        },
      ),
    );
  }
  
  Widget _buildHistoryCard(TradingSignal signal) {
    final color = signal.type == 'BUY' ? Colors.green :
                  signal.type == 'SELL' ? Colors.red :
                  Colors.orange;
    final icon = signal.type == 'BUY' ? Icons.trending_up :
                 signal.type == 'SELL' ? Icons.trending_down :
                 Icons.remove;
    
    String result = 'Active';
    IconData resultIcon = Icons.timer;
    Color resultColor = Colors.orange;
    
    if (signal.tp1Hit) {
      result = 'TP Hit';
      resultIcon = Icons.emoji_events;
      resultColor = Colors.green;
    } else if (signal.slHit) {
      result = 'SL Hit';
      resultIcon = Icons.warning;
      resultColor = Colors.red;
    }
    
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: color.withOpacity(0.2),
          child: Icon(icon, color: color),
        ),
        title: Row(
          children: [
            Text(
              '${signal.type} Signal',
              style: TextStyle(
                fontWeight: FontWeight.bold,
                color: color,
              ),
            ),
            const Spacer(),
            Icon(resultIcon, size: 16, color: resultColor),
            const SizedBox(width: 4),
            Text(
              result,
              style: TextStyle(fontSize: 12, color: resultColor),
            ),
          ],
        ),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SizedBox(height: 4),
            Text(
              'Entry: ${signal.entry.toStringAsFixed(5)} | Conf: ${signal.confidence.toStringAsFixed(0)}%',
              style: const TextStyle(fontSize: 12),
            ),
            Text(
              _formatTime(signal.generatedAt),
              style: const TextStyle(fontSize: 10, color: Colors.grey),
            ),
          ],
        ),
        trailing: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            if (signal.tp1Hit)
              const Icon(Icons.check_circle, color: Colors.green, size: 20),
            if (signal.slHit)
              const Icon(Icons.cancel, color: Colors.red, size: 20),
          ],
        ),
      ),
    );
  }
  
  String _formatTime(DateTime time) {
    return '${time.day}/${time.month} ${time.hour.toString().padLeft(2, '0')}:${time.minute.toString().padLeft(2, '0')}';
  }
}