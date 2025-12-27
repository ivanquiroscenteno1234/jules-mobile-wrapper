import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'config.dart';
import 'chat_screen.dart';
import 'sessions_screen.dart';
import 'dashboard_screen.dart';
import 'main.dart';
import 'test_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  List<dynamic> repos = [];
  bool isLoading = true;
  String? error;

  @override
  void initState() {
    super.initState();
    fetchRepos();
  }

  Future<void> fetchRepos() async {
    try {
      final response = await http.get(
        Uri.parse('${AppConfig.serverUrl}/repos'),
        headers: {'ngrok-skip-browser-warning': 'true'},
      );

      if (response.statusCode == 200) {
        setState(() {
          repos = json.decode(response.body);
          isLoading = false;
        });
      } else {
        setState(() {
          error = 'Failed to load repos: ${response.statusCode}';
          isLoading = false;
        });
      }
    } catch (e) {
      setState(() {
        error = 'Error connecting to server: $e\n\nMake sure python server is running!';
        isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Mobile Jules'),
        backgroundColor: Theme.of(context).colorScheme.inversePrimary,
        actions: [
          IconButton(
            icon: const Icon(Icons.science),
            tooltip: 'Test App',
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const TestScreen()),
              );
            },
          ),
          IconButton(
            icon: const Icon(Icons.dashboard),
            tooltip: 'Dashboard',
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const DashboardScreen()),
              );
            },
          ),
          IconButton(
            icon: const Icon(Icons.history),
            tooltip: 'Recent Sessions',
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const SessionsScreen()),
              );
            },
          ),
          IconButton(
            icon: const Icon(Icons.settings),
            onPressed: _showSettingsDialog,
          ),
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () {
              setState(() {
                isLoading = true;
                error = null;
              });
              fetchRepos();
            },
          )
        ],
      ),
      body: isLoading
          ? const Center(child: CircularProgressIndicator())
          : error != null
              ? Center(
                  child: Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: Text(error!, style: const TextStyle(color: Colors.red)),
                ))
              : Column(
                  children: [
                    // Automation Mode Toggle
                    Container(
                      margin: const EdgeInsets.all(16),
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                      decoration: BoxDecoration(
                        color: Colors.deepPurple[50],
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Row(
                        children: [
                          const Icon(Icons.auto_mode, color: Colors.deepPurple),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                const Text(
                                  'Auto Mode',
                                  style: TextStyle(fontWeight: FontWeight.bold),
                                ),
                                Text(
                                  AppConfig.autoMode
                                      ? 'Auto-approve plans & create PRs'
                                      : 'Manual plan approval',
                                  style: TextStyle(fontSize: 12, color: Colors.grey[600]),
                                ),
                              ],
                            ),
                          ),
                          Switch(
                            value: AppConfig.autoMode,
                            onChanged: (value) {
                              setState(() {
                                AppConfig.autoMode = value;
                              });
                            },
                            activeColor: Colors.deepPurple,
                          ),
                        ],
                      ),
                    ),
                    
                    // Section Title
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 16),
                      child: Row(
                        children: [
                          const Icon(Icons.folder, color: Colors.deepPurple),
                          const SizedBox(width: 8),
                          const Text(
                            'Your Repositories',
                            style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                          ),
                          const Spacer(),
                          Text(
                            '${repos.length} repos',
                            style: TextStyle(color: Colors.grey[600]),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 8),
                    
                    // Repos List
                    Expanded(
                      child: ListView.builder(
                        itemCount: repos.length,
                        itemBuilder: (context, index) {
                          final repo = repos[index];
                          return Card(
                            margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                            child: ListTile(
                              leading: CircleAvatar(
                                backgroundColor: Colors.deepPurple[100],
                                child: const Icon(Icons.code, color: Colors.deepPurple),
                              ),
                              title: Text(repo['name']),
                              subtitle: Text(repo['full_name']),
                              trailing: const Icon(Icons.chevron_right),
                              onTap: () {
                                Navigator.push(
                                  context,
                                  MaterialPageRoute(
                                    builder: (context) => ChatScreen(
                                      repoName: repo['name'],
                                      sourceId: repo['id'],
                                    ),
                                  ),
                                );
                              },
                            ),
                          );
                        },
                      ),
                    ),
                  ],
                ),
    );
  }

  void _showSettingsDialog() {
    final TextEditingController urlController = TextEditingController(text: AppConfig.serverUrl);
    bool localDarkMode = AppConfig.darkMode;
    
    showDialog(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('Settings'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Server URL
              const Text('Server URL:', style: TextStyle(fontWeight: FontWeight.bold)),
              const SizedBox(height: 4),
              TextField(
                controller: urlController,
                decoration: const InputDecoration(hintText: 'http://...'),
              ),
              
              const SizedBox(height: 16),
              const Divider(),
              const SizedBox(height: 8),
              
              // Dark Mode Toggle
              Row(
                children: [
                  const Icon(Icons.dark_mode),
                  const SizedBox(width: 12),
                  const Expanded(child: Text('Dark Mode')),
                  Switch(
                    value: localDarkMode,
                    onChanged: (value) {
                      setDialogState(() {
                        localDarkMode = value;
                      });
                    },
                  ),
                ],
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text('Cancel'),
            ),
            TextButton(
              onPressed: () {
                // Apply settings
                setState(() {
                  AppConfig.serverUrl = urlController.text.trim();
                  if (AppConfig.serverUrl.endsWith('/')) {
                    AppConfig.serverUrl = AppConfig.serverUrl.substring(0, AppConfig.serverUrl.length - 1);
                  }
                  AppConfig.darkMode = localDarkMode;
                  isLoading = true;
                  error = null;
                });
                
                // Apply theme
                MyApp.setThemeMode(
                  context, 
                  localDarkMode ? ThemeMode.dark : ThemeMode.light,
                );
                
                Navigator.pop(dialogContext);
                fetchRepos();
              },
              child: const Text('Save'),
            ),
          ],
        ),
      ),
    );
  }
}
