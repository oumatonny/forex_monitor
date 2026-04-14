// lib/screens/signal_screen.dart
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:fl_chart/fl_chart.dart';
import '../providers/trading_provider.dart';

class SignalScreen extends StatelessWidget {
  const SignalScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Signal Chart'),
        centerTitle: true,
      ),
      body: Consumer<TradingProvider>(
        builder: (context, provider, child) {
          if (provider.currentSignal == null) {
            return const Center(child: CircularProgressIndicator());
          }
          
          final signal = provider.currentSignal!;
          
          return SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Chart
                Container(
                  height: 300,
                  decoration: BoxDecoration(
                    color: const Color(0xFF1A2A3A),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.all(8),
                    child: LineChart(
                      _createChartData(signal),
                    ),
                  ),
                ),
                const SizedBox(height: 20),
                
                // Signal Levels
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Signal Levels',
                          style: TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 12),
                        _buildLevelRow('ENTRY', signal.entry, Colors.yellow),
                        _buildLevelRow('TP1', signal.tp1, Colors.green, signal.tp1Hit),
                        _buildLevelRow('TP2', signal.tp2, Colors.green, signal.tp2Hit),
                        _buildLevelRow('TP3', signal.tp3, Colors.green, signal.tp3Hit),
                        _buildLevelRow('STOP LOSS', signal.sl, Colors.red, signal.slHit),
                      ],
                    ),
                  ),
                ),
                
                const SizedBox(height: 16),
                
                // Momentum Indicators
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Momentum Analysis',
                          style: TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 12),
                        _buildMomentumRow('Signal Type', signal.type),
                        _buildMomentumRow('Confidence', '${signal.confidence.toStringAsFixed(0)}%'),
                        _buildMomentumRow('Expected Move', '${(signal.expectedMove * 10000).toStringAsFixed(1)} pips'),
                        _buildMomentumRow('Risk/Reward', '1:${_calculateRiskReward(signal).toStringAsFixed(2)}'),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
  
  LineChartData _createChartData(TradingSignal signal) {
    final spots = [
      const FlSpot(0, 1.0890),
      const FlSpot(1, 1.0895),
      const FlSpot(2, 1.0892),
      const FlSpot(3, 1.0898),
      const FlSpot(4, 1.0894),
    ];
    
    return LineChartData(
      gridData: const FlGridData(show: true),
      titlesData: const FlTitlesData(show: true),
      borderData: FlBorderData(show: true),
      lineBarsData: [
        LineChartBarData(
          spots: spots,
          isCurved: true,
          color: signal.type == 'BUY' ? Colors.green : Colors.red,
          barWidth: 3,
          dotData: const FlDotData(show: true),
        ),
      ],
    );
  }
  
  Widget _buildLevelRow(String label, double value, Color color, [bool isHit = false]) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Row(
            children: [
              Icon(Icons.circle, size: 12, color: color),
              const SizedBox(width: 8),
              Text(label),
            ],
          ),
          Row(
            children: [
              Text(
                value.toStringAsFixed(5),
                style: TextStyle(
                  fontWeight: FontWeight.bold,
                  color: color,
                ),
              ),
              if (isHit) ...[
                const SizedBox(width: 8),
                const Icon(Icons.check_circle, size: 16, color: Colors.green),
              ],
            ],
          ),
        ],
      ),
    );
  }
  
  Widget _buildMomentumRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(color: Colors.grey)),
          Text(value, style: const TextStyle(fontWeight: FontWeight.bold)),
        ],
      ),
    );
  }
  
  double _calculateRiskReward(TradingSignal signal) {
    final risk = (signal.sl - signal.entry).abs();
    final reward = (signal.tp2 - signal.entry).abs();
    return reward / risk;
  }
}