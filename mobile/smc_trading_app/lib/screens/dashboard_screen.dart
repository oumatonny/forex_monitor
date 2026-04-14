// lib/screens/dashboard_screen.dart
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/trading_provider.dart';
import '../widgets/price_card.dart';
import '../widgets/signal_card.dart';
import '../widgets/timer_card.dart';
import '../widgets/connection_button.dart';

class DashboardScreen extends StatelessWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Consumer<TradingProvider>(
        builder: (context, provider, child) {
          return RefreshIndicator(
            onRefresh: () async {
              await provider.connectToMT5();
            },
            child: CustomScrollView(
              slivers: [
                SliverAppBar(
                  title: const Text('SMC Trading App'),
                  actions: [
                    ConnectionButton(provider: provider),
                  ],
                  floating: true,
                  pinned: true,
                ),
                SliverPadding(
                  padding: const EdgeInsets.all(16),
                  sliver: SliverList(
                    delegate: SliverChildListDelegate([
                      // Price Card
                      if (provider.currentPrice != null)
                        PriceCard(priceData: provider.currentPrice!),
                      const SizedBox(height: 16),
                      
                      // Timer Card
                      if (provider.currentSignal != null)
                        TimerCard(remaining: provider.remainingValidity),
                      const SizedBox(height: 16),
                      
                      // Active Signal
                      if (provider.currentSignal != null)
                        SignalCard(signal: provider.currentSignal!),
                      const SizedBox(height: 16),
                      
                      // Quick Stats
                      _buildStatsCard(provider),
                      const SizedBox(height: 16),
                      
                      // Navigation Buttons
                      _buildNavigationButtons(context),
                    ]),
                  ),
                ),
              ],
            ),
          );
        },
      ),
      bottomNavigationBar: _buildBottomNavBar(context),
    );
  }
  
  Widget _buildStatsCard(TradingProvider provider) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceAround,
          children: [
            _buildStatItem(
              'Balance',
              provider.isConnected ? 'Connected' : 'Offline',
              provider.isConnected ? Colors.green : Colors.red,
            ),
            _buildStatItem(
              'Signal Age',
              provider.currentSignal != null
                  ? _formatDuration(DateTime.now().difference(provider.currentSignal!.generatedAt))
                  : 'No Signal',
              Colors.orange,
            ),
            _buildStatItem(
              'History',
              '${provider.signalHistory.length} signals',
              Colors.blue,
            ),
          ],
        ),
      ),
    );
  }
  
  Widget _buildStatItem(String label, String value, Color color) {
    return Column(
      children: [
        Text(
          label,
          style: const TextStyle(fontSize: 12, color: Colors.grey),
        ),
        const SizedBox(height: 4),
        Text(
          value,
          style: TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.bold,
            color: color,
          ),
        ),
      ],
    );
  }
  
  Widget _buildNavigationButtons(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: ElevatedButton.icon(
            onPressed: () => Navigator.pushNamed(context, '/signals'),
            icon: const Icon(Icons.timeline),
            label: const Text('View Chart'),
            style: ElevatedButton.styleFrom(
              padding: const EdgeInsets.symmetric(vertical: 12),
            ),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: OutlinedButton.icon(
            onPressed: () => Navigator.pushNamed(context, '/history'),
            icon: const Icon(Icons.history),
            label: const Text('History'),
            style: OutlinedButton.styleFrom(
              padding: const EdgeInsets.symmetric(vertical: 12),
            ),
          ),
        ),
      ],
    );
  }
  
  Widget _buildBottomNavBar(BuildContext context) {
    return BottomNavigationBar(
      currentIndex: 0,
      onTap: (index) {
        if (index == 1) Navigator.pushNamed(context, '/signals');
        if (index == 2) Navigator.pushNamed(context, '/history');
      },
      items: const [
        BottomNavigationBarItem(icon: Icon(Icons.dashboard), label: 'Dashboard'),
        BottomNavigationBarItem(icon: Icon(Icons.show_chart), label: 'Chart'),
        BottomNavigationBarItem(icon: Icon(Icons.history), label: 'History'),
      ],
    );
  }
  
  String _formatDuration(Duration duration) {
    final minutes = duration.inMinutes;
    if (minutes < 1) return '< 1 min';
    return '$minutes min';
  }
}