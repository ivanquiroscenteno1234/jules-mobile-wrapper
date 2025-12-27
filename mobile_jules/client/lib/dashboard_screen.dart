import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'config.dart';
import 'sessions_screen.dart';
import 'chat_screen.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  bool isLoading = true;
  String? error;
  int totalSessions = 0;
  int activeSessions = 0;
  int waitingSessions = 0;
  int completedSessions = 0;
  int sessionsWithPRs = 0;
  List<Map<String, dynamic>> recentSessions = [];

  @override
  void initState() {
    super.initState();
    fetchDashboardData();
  }

  Future<void> fetchDashboardData() async {
    setState(() {
      isLoading = true;
      error = null;
    });

    try {
      final response = await http.get(
        Uri.parse('${AppConfig.serverUrl}/sessions'),
        headers: {'ngrok-skip-browser-warning': 'true'},
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        final sessions = data['sessions'] as List? ?? [];
        
        int active = 0;
        int waiting = 0;
        int completed = 0;
        int withPRs = 0;
        
        for (var session in sessions) {
          final state = (session['state'] ?? '').toString().toUpperCase();
          switch (state) {
            case 'PLANNING':
            case 'WORKING':
              active++;
              break;
            case 'WAITING_FOR_USER':
              waiting++;
              break;
            case 'DONE':
              completed++;
              if (session['outputs'] != null && (session['outputs'] as List).isNotEmpty) {
                withPRs++;
              }
              break;
          }
        }
        
        setState(() {
          totalSessions = sessions.length;
          activeSessions = active;
          waitingSessions = waiting;
          completedSessions = completed;
          sessionsWithPRs = withPRs;
          recentSessions = sessions.take(5).cast<Map<String, dynamic>>().toList();
          isLoading = false;
        });
      } else {
        setState(() {
          error = 'Failed to load: ${response.statusCode}';
          isLoading = false;
        });
      }
    } catch (e) {
      setState(() {
        error = 'Error: $e';
        isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Dashboard'),
        backgroundColor: Theme.of(context).colorScheme.inversePrimary,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: fetchDashboardData,
          ),
        ],
      ),
      body: isLoading
          ? const Center(child: CircularProgressIndicator())
          : error != null
              ? Center(child: Text(error!, style: const TextStyle(color: Colors.red)))
              : RefreshIndicator(
                  onRefresh: fetchDashboardData,
                  child: SingleChildScrollView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        // Stats Grid
                        GridView.count(
                          crossAxisCount: 2,
                          shrinkWrap: true,
                          physics: const NeverScrollableScrollPhysics(),
                          mainAxisSpacing: 12,
                          crossAxisSpacing: 12,
                          childAspectRatio: 1.5,
                          children: [
                            _buildStatCard(
                              'Active',
                              activeSessions.toString(),
                              Icons.code,
                              Colors.orange,
                            ),
                            _buildStatCard(
                              'Waiting',
                              waitingSessions.toString(),
                              Icons.pending_actions,
                              Colors.amber,
                            ),
                            _buildStatCard(
                              'Completed',
                              completedSessions.toString(),
                              Icons.check_circle,
                              Colors.green,
                            ),
                            _buildStatCard(
                              'PRs Created',
                              sessionsWithPRs.toString(),
                              Icons.merge,
                              Colors.purple,
                            ),
                          ],
                        ),
                        
                        const SizedBox(height: 24),
                        
                        // Quick Actions
                        const Text(
                          'Quick Actions',
                          style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                        ),
                        const SizedBox(height: 12),
                        Row(
                          children: [
                            Expanded(
                              child: _buildActionButton(
                                'View All Sessions',
                                Icons.list,
                                () => Navigator.push(
                                  context,
                                  MaterialPageRoute(builder: (_) => const SessionsScreen()),
                                ),
                              ),
                            ),
                          ],
                        ),
                        
                        if (waitingSessions > 0) ...[
                          const SizedBox(height: 16),
                          Container(
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: Colors.amber[50],
                              borderRadius: BorderRadius.circular(8),
                              border: Border.all(color: Colors.amber),
                            ),
                            child: Row(
                              children: [
                                const Icon(Icons.warning_amber, color: Colors.amber),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: Text(
                                    '$waitingSessions session(s) waiting for your input',
                                    style: const TextStyle(fontWeight: FontWeight.w500),
                                  ),
                                ),
                                TextButton(
                                  onPressed: () => Navigator.push(
                                    context,
                                    MaterialPageRoute(builder: (_) => const SessionsScreen()),
                                  ),
                                  child: const Text('View'),
                                ),
                              ],
                            ),
                          ),
                        ],
                        
                        const SizedBox(height: 24),
                        
                        // Recent Sessions
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            const Text(
                              'Recent Sessions',
                              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                            ),
                            TextButton(
                              onPressed: () => Navigator.push(
                                context,
                                MaterialPageRoute(builder: (_) => const SessionsScreen()),
                              ),
                              child: const Text('See All'),
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        if (recentSessions.isEmpty)
                          const Center(
                            child: Padding(
                              padding: EdgeInsets.all(32),
                              child: Text('No sessions yet', style: TextStyle(color: Colors.grey)),
                            ),
                          )
                        else
                          ...recentSessions.map((s) => _buildSessionTile(s)).toList(),
                      ],
                    ),
                  ),
                ),
    );
  }

  Widget _buildStatCard(String label, String value, IconData icon, Color color) {
    return Card(
      elevation: 2,
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(8),
          gradient: LinearGradient(
            colors: [color.withOpacity(0.1), color.withOpacity(0.05)],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Row(
              children: [
                Icon(icon, color: color, size: 20),
                const Spacer(),
                Text(
                  value,
                  style: TextStyle(
                    fontSize: 28,
                    fontWeight: FontWeight.bold,
                    color: color,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              label,
              style: TextStyle(color: Colors.grey[600]),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildActionButton(String label, IconData icon, VoidCallback onPressed) {
    return ElevatedButton.icon(
      onPressed: onPressed,
      icon: Icon(icon),
      label: Text(label),
      style: ElevatedButton.styleFrom(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        backgroundColor: Colors.deepPurple,
        foregroundColor: Colors.white,
      ),
    );
  }

  Widget _buildSessionTile(Map<String, dynamic> session) {
    final state = (session['state'] ?? '').toString().toUpperCase();
    final title = session['title'] ?? 'Untitled';
    
    Color statusColor;
    IconData statusIcon;
    
    switch (state) {
      case 'PLANNING':
        statusColor = Colors.blue;
        statusIcon = Icons.edit_note;
        break;
      case 'WORKING':
        statusColor = Colors.orange;
        statusIcon = Icons.code;
        break;
      case 'WAITING_FOR_USER':
        statusColor = Colors.amber;
        statusIcon = Icons.pending_actions;
        break;
      case 'DONE':
        statusColor = Colors.green;
        statusIcon = Icons.check_circle;
        break;
      default:
        statusColor = Colors.grey;
        statusIcon = Icons.help_outline;
    }
    
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: statusColor.withOpacity(0.2),
          child: Icon(statusIcon, color: statusColor, size: 20),
        ),
        title: Text(title, maxLines: 1, overflow: TextOverflow.ellipsis),
        subtitle: Text(state.replaceAll('_', ' ')),
        trailing: const Icon(Icons.chevron_right),
        onTap: () {
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => ChatScreen(
                repoName: title,
                sourceId: session['sourceContext']?['source'] ?? '',
                sessionId: session['name'],
              ),
            ),
          );
        },
      ),
    );
  }
}
