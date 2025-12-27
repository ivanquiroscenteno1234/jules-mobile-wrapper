import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:url_launcher/url_launcher.dart';
import 'config.dart';
import 'chat_screen.dart';

class PullRequest {
  final String url;
  final String title;
  final String? description;

  PullRequest({required this.url, required this.title, this.description});

  factory PullRequest.fromJson(Map<String, dynamic> json) {
    return PullRequest(
      url: json['url'] ?? '',
      title: json['title'] ?? 'Pull Request',
      description: json['description'],
    );
  }
}

class Session {
  final String name;
  final String id;
  final String title;
  final String? state;
  final String? sourceContext;
  final String? prompt;
  final List<PullRequest> pullRequests;

  Session({
    required this.name,
    required this.id,
    required this.title,
    this.state,
    this.sourceContext,
    this.prompt,
    this.pullRequests = const [],
  });

  factory Session.fromJson(Map<String, dynamic> json) {
    List<PullRequest> prs = [];
    if (json['outputs'] != null) {
      for (var output in json['outputs']) {
        if (output['pullRequest'] != null) {
          prs.add(PullRequest.fromJson(output['pullRequest']));
        }
      }
    }
    
    return Session(
      name: json['name'] ?? '',
      id: json['id'] ?? '',
      title: json['title'] ?? 'Untitled Session',
      state: json['state'],
      sourceContext: json['sourceContext']?['source'],
      prompt: json['prompt'],
      pullRequests: prs,
    );
  }

  String get displayTitle => title.isNotEmpty ? title : 'Session ${id.substring(0, 8)}...';
  
  bool get hasPR => pullRequests.isNotEmpty;
  
  String get statusText {
    switch (state?.toUpperCase()) {
      case 'PLANNING':
        return 'Planning';
      case 'WORKING':
        return 'Working';
      case 'WAITING_FOR_USER':
        return 'Waiting for input';
      case 'DONE':
        return hasPR ? 'PR Created' : 'Completed';
      default:
        return state ?? 'Unknown';
    }
  }

  Color get statusColor {
    switch (state?.toUpperCase()) {
      case 'PLANNING':
        return Colors.blue;
      case 'WORKING':
        return Colors.orange;
      case 'WAITING_FOR_USER':
        return Colors.amber;
      case 'DONE':
        return Colors.green;
      default:
        return Colors.grey;
    }
  }

  IconData get statusIcon {
    switch (state?.toUpperCase()) {
      case 'PLANNING':
        return Icons.edit_note;
      case 'WORKING':
        return Icons.code;
      case 'WAITING_FOR_USER':
        return Icons.pending_actions;
      case 'DONE':
        return hasPR ? Icons.merge : Icons.check_circle;
      default:
        return Icons.help_outline;
    }
  }
}

class SessionsScreen extends StatefulWidget {
  const SessionsScreen({super.key});

  @override
  State<SessionsScreen> createState() => _SessionsScreenState();
}

class _SessionsScreenState extends State<SessionsScreen> {
  List<Session> sessions = [];
  bool isLoading = true;
  String? error;

  @override
  void initState() {
    super.initState();
    fetchSessions();
  }

  Future<void> fetchSessions() async {
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
        final sessionsList = data['sessions'] as List? ?? [];
        
        setState(() {
          sessions = sessionsList
              .map((s) => Session.fromJson(s))
              .toList();
          isLoading = false;
        });
      } else {
        setState(() {
          error = 'Failed to load sessions: ${response.statusCode}';
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

  void _reconnectToSession(Session session) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => ChatScreen(
          repoName: session.displayTitle,
          sourceId: session.sourceContext ?? '',
          sessionId: session.name,
        ),
      ),
    );
  }

  Future<void> _openPR(PullRequest pr) async {
    final uri = Uri.parse(pr.url);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
  }

  Future<bool> _deleteSession(Session session) async {
    // Show confirmation dialog
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Session?'),
        content: Text('Are you sure you want to delete "${session.displayTitle}"? This cannot be undone.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            style: TextButton.styleFrom(foregroundColor: Colors.red),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    
    if (confirmed != true) return false;
    
    try {
      final response = await http.delete(
        Uri.parse('${AppConfig.serverUrl}/sessions/${session.id}'),
        headers: {'ngrok-skip-browser-warning': 'true'},
      );
      
      if (response.statusCode == 200) {
        // Remove from local list
        setState(() {
          sessions.removeWhere((s) => s.id == session.id);
        });
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Session deleted')),
          );
        }
        return true;
      } else {
        throw Exception('Failed to delete session');
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e')),
        );
      }
      return false;
    }
  }

  void _showSessionDetails(Session session) {
    showModalBottomSheet(
      context: context,
      builder: (context) => Container(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              session.displayTitle,
              style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            Text(
              'Status: ${session.statusText}',
              style: TextStyle(color: session.statusColor),
            ),
            if (session.prompt != null) ...[
              const SizedBox(height: 8),
              Text(
                'Task: ${session.prompt}',
                style: TextStyle(color: Colors.grey[600]),
                maxLines: 3,
                overflow: TextOverflow.ellipsis,
              ),
            ],
            const SizedBox(height: 16),
            
            // PRs Section
            if (session.hasPR) ...[
              const Text(
                'Pull Requests',
                style: TextStyle(fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 8),
              ...session.pullRequests.map((pr) => Card(
                color: Colors.green[50],
                child: ListTile(
                  leading: const Icon(Icons.merge, color: Colors.green),
                  title: Text(pr.title, maxLines: 1, overflow: TextOverflow.ellipsis),
                  subtitle: Text(pr.url, maxLines: 1, overflow: TextOverflow.ellipsis),
                  trailing: const Icon(Icons.open_in_new),
                  onTap: () => _openPR(pr),
                ),
              )).toList(),
              const SizedBox(height: 16),
            ],
            
            // Actions
            Row(
              children: [
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: () {
                      Navigator.pop(context);
                      _reconnectToSession(session);
                    },
                    icon: const Icon(Icons.chat),
                    label: const Text('Open Chat'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.deepPurple,
                      foregroundColor: Colors.white,
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Recent Sessions'),
        backgroundColor: Theme.of(context).colorScheme.inversePrimary,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: fetchSessions,
          ),
        ],
      ),
      body: isLoading
          ? const Center(child: CircularProgressIndicator())
          : error != null
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(error!, style: const TextStyle(color: Colors.red)),
                      const SizedBox(height: 16),
                      ElevatedButton(
                        onPressed: fetchSessions,
                        child: const Text('Retry'),
                      ),
                    ],
                  ),
                )
              : sessions.isEmpty
                  ? const Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.inbox, size: 64, color: Colors.grey),
                          SizedBox(height: 16),
                          Text('No sessions yet',
                              style: TextStyle(color: Colors.grey)),
                        ],
                      ),
                    )
                  : RefreshIndicator(
                      onRefresh: fetchSessions,
                      child: ListView.builder(
                        itemCount: sessions.length,
                        itemBuilder: (context, index) {
                          final session = sessions[index];
                          return Dismissible(
                            key: Key(session.id),
                            direction: DismissDirection.endToStart,
                            background: Container(
                              alignment: Alignment.centerRight,
                              padding: const EdgeInsets.only(right: 20),
                              margin: const EdgeInsets.symmetric(
                                horizontal: 16,
                                vertical: 8,
                              ),
                              decoration: BoxDecoration(
                                color: Colors.red,
                                borderRadius: BorderRadius.circular(12),
                              ),
                              child: const Icon(
                                Icons.delete,
                                color: Colors.white,
                              ),
                            ),
                            confirmDismiss: (direction) => _deleteSession(session),
                            child: Card(
                              margin: const EdgeInsets.symmetric(
                                horizontal: 16,
                                vertical: 8,
                              ),
                              child: ListTile(
                                leading: CircleAvatar(
                                  backgroundColor: session.statusColor.withOpacity(0.2),
                                  child: Icon(
                                    session.statusIcon,
                                    color: session.statusColor,
                                  ),
                                ),
                                title: Text(
                                  session.displayTitle,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                ),
                                subtitle: Row(
                                  children: [
                                    Text(
                                      session.statusText,
                                      style: TextStyle(color: session.statusColor),
                                    ),
                                    if (session.hasPR) ...[
                                      const SizedBox(width: 8),
                                      Container(
                                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                        decoration: BoxDecoration(
                                          color: Colors.green[100],
                                          borderRadius: BorderRadius.circular(4),
                                        ),
                                        child: const Row(
                                          mainAxisSize: MainAxisSize.min,
                                          children: [
                                            Icon(Icons.merge, size: 12, color: Colors.green),
                                            SizedBox(width: 2),
                                            Text('PR', style: TextStyle(fontSize: 10, color: Colors.green)),
                                          ],
                                        ),
                                      ),
                                    ],
                                  ],
                                ),
                                trailing: const Icon(Icons.chevron_right),
                                onTap: () => _showSessionDetails(session),
                              ),
                            ),
                          );
                        },
                      ),
                    ),
    );
  }
}
