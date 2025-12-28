import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'config.dart';
import 'chat_screen.dart';
import 'sessions_screen.dart';
import 'dashboard_screen.dart';
import 'github_repos_screen.dart';
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
            icon: const Icon(Icons.folder_copy_outlined),
            tooltip: 'GitHub Repos',
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const GitHubReposScreen()),
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
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _showNewTaskDialog,
        icon: const Icon(Icons.add),
        label: const Text('New Task'),
        backgroundColor: Colors.deepPurple,
        foregroundColor: Colors.white,
      ),
    );
  }

  void _showNewTaskDialog() {
    final TextEditingController promptController = TextEditingController();
    final TextEditingController repoNameController = TextEditingController();
    bool noCodebase = false;
    bool autoCreatePR = false;  // Auto-create PR toggle
    bool isPrivateRepo = false;  // Private repo toggle for No Codebase
    bool isCreatingRepo = false;  // Loading state for repo creation
    String? createRepoError;  // Error message for repo creation
    String? selectedRepoId;
    String? selectedRepoName;
    
    showDialog(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('New Task'),
          content: ConstrainedBox(
            constraints: BoxConstraints(
              maxWidth: MediaQuery.of(context).size.width * 0.85,
              maxHeight: MediaQuery.of(context).size.height * 0.7,
            ),
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Task Prompt
                  const Text('What would you like Jules to do?', style: TextStyle(fontWeight: FontWeight.bold)),
                  const SizedBox(height: 8),
                  TextField(
                    controller: promptController,
                    minLines: 1,
                    maxLines: 5,
                    keyboardType: TextInputType.multiline,
                    textInputAction: TextInputAction.newline,
                    decoration: const InputDecoration(
                      hintText: 'e.g., Create a Flask app with user authentication...',
                      border: OutlineInputBorder(),
                    ),
                    onChanged: (_) => setDialogState(() {}),  // Rebuild to update button state
                  ),
                  const SizedBox(height: 16),
                  
                  // No Codebase Toggle (DISABLED - Coming Soon)
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    title: Row(
                      children: [
                        const Text('No Codebase'),
                        const SizedBox(width: 8),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(
                            color: Colors.orange[100],
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            'Coming Soon',
                            style: TextStyle(fontSize: 10, color: Colors.orange[800], fontWeight: FontWeight.bold),
                          ),
                        ),
                      ],
                    ),
                    subtitle: Text(
                      'Start from scratch (requires Jules web setup)',
                      style: TextStyle(fontSize: 12, color: Colors.grey[400]),
                    ),
                    value: false,
                    onChanged: null,  // Disabled
                    activeColor: Colors.deepPurple,
                  ),
                  
                  // No Codebase: Show repo creation options
                  if (noCodebase) ...[
                    const SizedBox(height: 8),
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: Colors.deepPurple[50],
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: Colors.deepPurple[200]!),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Icon(Icons.auto_awesome, color: Colors.deepPurple[700], size: 20),
                              const SizedBox(width: 8),
                              Text(
                                'Auto-Create GitHub Repository',
                                style: TextStyle(
                                  fontWeight: FontWeight.bold,
                                  color: Colors.deepPurple[700],
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 12),
                          const Text('Repository Name', style: TextStyle(fontWeight: FontWeight.w500)),
                          const SizedBox(height: 4),
                          TextField(
                            controller: repoNameController,
                            enabled: !isCreatingRepo,
                            decoration: InputDecoration(
                              hintText: 'my-new-project',
                              border: const OutlineInputBorder(),
                              filled: true,
                              fillColor: Colors.white,
                              errorText: createRepoError,
                            ),
                            onChanged: (_) => setDialogState(() {
                              createRepoError = null;
                            }),
                          ),
                          const SizedBox(height: 8),
                          SwitchListTile(
                            contentPadding: EdgeInsets.zero,
                            title: const Text('Private Repository', style: TextStyle(fontSize: 14)),
                            subtitle: Text(
                              isPrivateRepo ? 'Only you can see this repository' : 'Anyone can see this repository',
                              style: TextStyle(fontSize: 11, color: Colors.grey[600]),
                            ),
                            value: isPrivateRepo,
                            onChanged: isCreatingRepo ? null : (value) => setDialogState(() => isPrivateRepo = value),
                            activeColor: Colors.deepPurple,
                            dense: true,
                          ),
                        ],
                      ),
                    ),
                  ],
                  
                  // Repo Selection (only if noCodebase is false)
                  if (!noCodebase) ...[
                    const SizedBox(height: 8),
                    const Text('Repository', style: TextStyle(fontWeight: FontWeight.bold)),
                    const SizedBox(height: 4),
                    DropdownButtonFormField<String>(
                      value: selectedRepoId,
                      isExpanded: true,
                      hint: const Text('Select a repository'),
                      decoration: const InputDecoration(
                        border: OutlineInputBorder(),
                        contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 14),
                      ),
                      selectedItemBuilder: (BuildContext context) {
                        return repos.map<Widget>((repo) {
                          return Align(
                            alignment: Alignment.centerLeft,
                            child: Text(
                              repo['full_name'],
                              overflow: TextOverflow.ellipsis,
                              maxLines: 1,
                            ),
                          );
                        }).toList();
                      },
                      items: repos.map((repo) => DropdownMenuItem<String>(
                        value: repo['id'],
                        child: Text(
                          repo['full_name'],
                          overflow: TextOverflow.ellipsis,
                          maxLines: 1,
                        ),
                      )).toList(),
                      onChanged: (value) {
                        setDialogState(() {
                          selectedRepoId = value;
                          selectedRepoName = repos.firstWhere((r) => r['id'] == value)['name'];
                        });
                      },
                    ),
                    const SizedBox(height: 8),
                    // Auto-Create PR Toggle
                    SwitchListTile(
                      contentPadding: EdgeInsets.zero,
                      title: const Text('Auto-Create PR'),
                      subtitle: Text(
                        autoCreatePR 
                          ? 'Automatically create a pull request when done' 
                          : 'Manual PR creation after completion',
                        style: TextStyle(fontSize: 12, color: Colors.grey[600]),
                      ),
                      value: autoCreatePR,
                      onChanged: (value) {
                        setDialogState(() {
                          autoCreatePR = value;
                        });
                      },
                      activeColor: Colors.green,
                    ),
                  ],
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: isCreatingRepo ? null : () => Navigator.pop(dialogContext),
              child: const Text('Cancel'),
            ),
            ElevatedButton(
              onPressed: (promptController.text.trim().isEmpty || 
                         (!noCodebase && selectedRepoId == null) ||
                         (noCodebase && repoNameController.text.trim().isEmpty) ||
                         isCreatingRepo)
                ? null
                : () async {
                    if (noCodebase && repoNameController.text.trim().isNotEmpty) {
                      // Create GitHub repo first
                      setDialogState(() {
                        isCreatingRepo = true;
                        createRepoError = null;
                      });
                      
                      try {
                        final response = await http.post(
                          Uri.parse('${AppConfig.serverUrl}/github/repos'),
                          headers: {
                            'ngrok-skip-browser-warning': 'true',
                            'Content-Type': 'application/json',
                          },
                          body: jsonEncode({
                            'name': repoNameController.text.trim(),
                            'description': promptController.text.trim().substring(
                              0, 
                              promptController.text.trim().length > 100 ? 100 : promptController.text.trim().length
                            ),
                            'private': isPrivateRepo,
                          }),
                        );
                        
                        if (response.statusCode == 200) {
                          final data = jsonDecode(response.body);
                          Navigator.pop(dialogContext);
                          
                          // Show success message
                          if (mounted) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(
                                content: Text('Repository "${data['name']}" created!'),
                                backgroundColor: Colors.green,
                                duration: const Duration(seconds: 2),
                              ),
                            );
                          }
                          
                          // Navigate to ChatScreen with the new repo name (repoless mode)
                          Navigator.push(
                            context,
                            MaterialPageRoute(
                              builder: (context) => ChatScreen(
                                repoName: data['name'] ?? repoNameController.text.trim(),
                                sourceId: null,  // Still repoless for Jules
                                initialPrompt: promptController.text.trim(),
                                autoMode: false,
                              ),
                            ),
                          );
                        } else {
                          final errorData = jsonDecode(response.body);
                          setDialogState(() {
                            isCreatingRepo = false;
                            createRepoError = errorData['detail'] ?? 'Failed to create repository';
                          });
                        }
                      } catch (e) {
                        setDialogState(() {
                          isCreatingRepo = false;
                          createRepoError = 'Error: $e';
                        });
                      }
                    } else {
                      // Normal flow: existing repo or truly repoless
                      Navigator.pop(dialogContext);
                      Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (context) => ChatScreen(
                            repoName: noCodebase ? 'New Project' : (selectedRepoName ?? 'Project'),
                            sourceId: noCodebase ? null : selectedRepoId,
                            initialPrompt: promptController.text.trim(),
                            autoMode: autoCreatePR,
                          ),
                        ),
                      );
                    }
                  },
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.deepPurple,
                foregroundColor: Colors.white,
              ),
              child: isCreatingRepo 
                ? const SizedBox(
                    width: 20, 
                    height: 20, 
                    child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white)
                  )
                : Text(noCodebase && repoNameController.text.trim().isNotEmpty ? 'Create & Start' : 'Start'),
            ),
          ],
        ),
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
