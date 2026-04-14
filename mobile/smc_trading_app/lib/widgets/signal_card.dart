
// lib/widgets/signal_card.dart
import 'package:flutter/material.dart';
import '../models/trading_models.dart';

class SignalCard extends StatelessWidget {
  final TradingSignal signal;
  
  const SignalCard({super.key, required this.signal});
  
  @override
  Widget build(BuildContext context) {
    final isBuy = signal.type == 'BUY';
    final isSell = signal.type == 'SELL';
    final color = isBuy ? Colors.green : isSell ? Colors.red : Colors.orange;
    final icon = isBuy ? Icons.trending_up : isSell ? Icons.trending_down : Icons.remove;
    
    return Card(
      elevation: 4,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: color, width: 2),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(icon, size: 28, color: color),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '${signal.type} SIGNAL ACTIVE',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                          color: color,
                        ),
                      ),
                      Text(
                        'Confidence: ${signal.confidence.toStringAsFixed(0)}%',
                        style: const TextStyle(fontSize: 12),
                      ),
                    ],
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                  decoration: BoxDecoration(
                    color: color,
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: const Text(
                    'LIVE',
                    style: TextStyle(color: Colors.white, fontSize: 10),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            _buildLevelRow('ENTRY', signal.entry, Colors.yellow),
            const SizedBox(height: 8),
            const Text('TAKE PROFIT', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
            const SizedBox(height: 4),
            Row(
              children: [
                Expanded(child: _buildTPCard('TP1', signal.tp1, signal.tp1Hit)),
                const SizedBox(width: 8),
                Expanded(child: _buildTPCard('TP2', signal.tp2, signal.tp2Hit)),
                const SizedBox(width: 8),
                Expanded(child: _buildTPCard('TP3', signal.tp3, signal.tp3Hit)),
              ],
            ),
            const SizedBox(height: 8),
            _buildLevelRow('STOP LOSS', signal.sl, Colors.red),
          ],
        ),
      ),
    );
  }
  
  Widget _buildLevelRow(String title, double value, Color color) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFF0E1A2B),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(title, style: const TextStyle(fontWeight: FontWeight.bold)),
          Text(
            value.toStringAsFixed(5),
            style: TextStyle(
              fontWeight: FontWeight.bold,
              color: color,
            ),
          ),
        ],
      ),
    );
  }
  
  Widget _buildTPCard(String level, double price, bool isHit) {
    return Container(
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: isHit ? Colors.green.withOpacity(0.2) : const Color(0xFF0E1A2B),
        borderRadius: BorderRadius.circular(8),
        border: isHit ? Border.all(color: Colors.green) : null,
      ),
      child: Column(
        children: [
          Text(level, style: const TextStyle(fontSize: 11)),
          const SizedBox(height: 4),
          Text(
            price.toStringAsFixed(5),
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.bold,
              color: isHit ? Colors.green : Colors.white,
            ),
          ),
          if (isHit) const Icon(Icons.check_circle, size: 12, color: Colors.green),
        ],
      ),
    );
  }
}
