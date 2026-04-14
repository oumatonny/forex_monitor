// lib/widgets/price_card.dart
import 'package:flutter/material.dart';
import '../models/trading_models.dart';

class PriceCard extends StatelessWidget {
  final PriceData priceData;
  
  const PriceCard({super.key, required this.priceData});
  
  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Expanded(
              child: _buildPriceBox('BID', priceData.bid, Colors.red),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _buildPriceBox('ASK', priceData.ask, Colors.green),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _buildPriceBox('SPREAD', priceData.spread * 10000, Colors.amber, isPips: true),
            ),
          ],
        ),
      ),
    );
  }
  
  Widget _buildPriceBox(String title, double value, Color color, {bool isPips = false}) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFF0E1A2B),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Column(
        children: [
          Text(
            title,
            style: const TextStyle(fontSize: 12, color: Colors.grey),
          ),
          const SizedBox(height: 4),
          Text(
            isPips ? '${value.toStringAsFixed(1)} pips' : value.toStringAsFixed(5),
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.bold,
              color: color,
              fontFamily: 'monospace',
            ),
          ),
        ],
      ),
    );
  }
}
