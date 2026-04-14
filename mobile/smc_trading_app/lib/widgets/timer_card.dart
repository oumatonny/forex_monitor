
// lib/widgets/timer_card.dart
import 'package:flutter/material.dart';

class TimerCard extends StatelessWidget {
  final Duration remaining;
  
  const TimerCard({super.key, required this.remaining});
  
  @override
  Widget build(BuildContext context) {
    final minutes = remaining.inMinutes.remainder(60).toString().padLeft(2, '0');
    final seconds = remaining.inSeconds.remainder(60).toString().padLeft(2, '0');
    final isValid = remaining.inSeconds > 0;
    
    return Card(
      color: isValid ? Colors.blue.withOpacity(0.1) : Colors.red.withOpacity(0.1),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            const Text(
              'SIGNAL VALID FOR',
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            Text(
              '$minutes:$seconds',
              style: TextStyle(
                fontSize: 32,
                fontWeight: FontWeight.bold,
                color: isValid ? Colors.blue : Colors.red,
                fontFamily: 'monospace',
              ),
            ),
            const SizedBox(height: 4),
            Text(
              'Next signal in 20 minutes',
              style: TextStyle(fontSize: 10, color: Colors.grey.shade600),
            ),
          ],
        ),
      ),
    );
  }
}
