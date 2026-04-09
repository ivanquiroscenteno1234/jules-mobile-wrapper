import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'config.dart';
import 'main.dart' show showNotification;

class TestScreen extends StatefulWidget {
  const TestScreen({super.key});

  @override
  State<TestScreen> createState() => _TestScreenState();
}

class _TestScreenState extends State<TestScreen> with SingleTickerProviderStateMixin {
  final _urlController = TextEditingController();
  final _objectiveController = TextEditingController();
  late TabController _tabController;
  
  bool _isRunning = false;
  String? _testId;
  Map<String, dynamic>? _testResult;
  Timer? _pollTimer;
  List<String> _urlHistory = [];
  
  // History state
  List<dynamic> _allTests = [];
  bool _isLoadingHistory = false;
  Map<String, dynamic>? _selectedHistoryTest;

  // Dropdown state
  List<Map<String, dynamic>> _repos = [];
  List<Map<String, dynamic>> _presets = [];
  List<Map<String, dynamic>> _creds = [];
  String? _selectedRepo;
  String? _selectedPresetId;
  String? _selectedCredId;
  bool _isLoadingRepos = true;
  bool _isLoadingData = false;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _tabController.addListener(() {
      if (_tabController.index == 1) {
        _loadTestHistory();
      }
    });
    _fetchUrlHistory();
    _loadRepos();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // Check for pre-filled arguments from the Chat-to-Test bridge
    final args = ModalRoute.of(context)?.settings.arguments;
    if (args != null && args is Map<String, dynamic>) {
      if (args['url'] != null && _urlController.text.isEmpty) {
        _urlController.text = args['url'] as String;
      }
      if (args['objective'] != null && _objectiveController.text.isEmpty) {
        _objectiveController.text = args['objective'] as String;
      }
      // Preselect repository from chat session
      if (args['repository'] != null && _selectedRepo == null) {
        String repoValue = args['repository'] as String;
        // Convert sourceId format (sources/github/owner/repo or repos/owner/repo) to full_name format (owner/repo)
        if (repoValue.startsWith('sources/github/')) {
          // Extract owner/repo from "sources/github/owner/repo"
          repoValue = repoValue.substring('sources/github/'.length);
        } else if (repoValue.startsWith('repos/')) {
          // Extract owner/repo from "repos/owner/repo"
          repoValue = repoValue.substring('repos/'.length);
        }
        // Now use repoName directly if it's in owner/repo format
        final displayName = args['repoName'] as String?;
        if (displayName != null && displayName.contains('/')) {
          repoValue = displayName;  // Use the display name which is already owner/repo
        }
        setState(() {
          _selectedRepo = repoValue;
        });
      }
    }
  }

  @override
  void dispose() {
    _urlController.dispose();
    _objectiveController.dispose();
    _tabController.dispose();
    _pollTimer?.cancel();
    super.dispose();
  }

  Future<void> _loadTestHistory() async {
    setState(() => _isLoadingHistory = true);
    try {
      final response = await http.get(
        Uri.parse('${AppConfig.serverUrl}/tests'),
        headers: {'ngrok-skip-browser-warning': 'true'},
      );
      if (response.statusCode == 200) {
        final data = json.decode(response.body) as List;
        setState(() {
          _allTests = data.reversed.toList(); // Newest first
          _isLoadingHistory = false;
        });
      }
    } catch (e) {
      print('Error loading history: $e');
      setState(() => _isLoadingHistory = false);
    }
  }

  Future<void> _loadRepos() async {
    try {
      final response = await http.get(
        Uri.parse('${AppConfig.serverUrl}/repos'),
        headers: {'ngrok-skip-browser-warning': 'true'},
      );
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        List<Map<String, dynamic>> reposList = [];
        if (data is List) {
          reposList = List<Map<String, dynamic>>.from(data);
        } else if (data is Map && data['repos'] is List) {
          reposList = List<Map<String, dynamic>>.from(data['repos']);
        }
        setState(() {
          _repos = reposList;
          _isLoadingRepos = false;
        });
      }
    } catch (e) {
      print('Error loading repos: $e');
      setState(() => _isLoadingRepos = false);
    }
  }

  Future<void> _loadPresetsAndCreds(String repoFullName) async {
    setState(() => _isLoadingData = true);
    
    final parts = repoFullName.split('/');
    if (parts.length != 2) return;
    
    try {
      // Fetch presets
      final presetsResponse = await http.get(
        Uri.parse('${AppConfig.serverUrl}/repos/${parts[0]}/${parts[1]}/presets'),
        headers: {'ngrok-skip-browser-warning': 'true'},
      );
      if (presetsResponse.statusCode == 200) {
        final data = json.decode(presetsResponse.body);
        if (data is List) {
          _presets = List<Map<String, dynamic>>.from(data);
        } else if (data is Map && data.containsKey('presets')) {
          _presets = List<Map<String, dynamic>>.from(data['presets']);
        } else {
          _presets = [];
        }
      }
      
      // Fetch credentials
      final credsResponse = await http.get(
        Uri.parse('${AppConfig.serverUrl}/repos/${parts[0]}/${parts[1]}/credentials'),
        headers: {'ngrok-skip-browser-warning': 'true'},
      );
      if (credsResponse.statusCode == 200) {
        final data = json.decode(credsResponse.body);
        if (data is List) {
          _creds = List<Map<String, dynamic>>.from(data);
        } else if (data is Map && data.containsKey('credentials')) {
          _creds = List<Map<String, dynamic>>.from(data['credentials']);
        } else {
          _creds = [];
        }
      }
    } catch (e) {
      print('Error loading data: $e');
    }
    
    setState(() {
      _isLoadingData = false;
      _selectedPresetId = null;
      _selectedCredId = null;
    });
  }

  void _onPresetSelected(String? presetId) {
    if (presetId == null) return;
    
    final preset = _presets.firstWhere((p) => p['id'] == presetId, orElse: () => {});
    if (preset.isNotEmpty) {
      setState(() {
        _selectedPresetId = presetId;
        _urlController.text = preset['url'] ?? '';
        _objectiveController.text = preset['objective'] ?? '';
      });
    }
  }

  Future<void> _fetchUrlHistory() async {
    try {
      final response = await http.get(
        Uri.parse('${AppConfig.serverUrl}/test/urls'),
        headers: {'ngrok-skip-browser-warning': 'true'},
      );
      if (response.statusCode == 200) {
        final data = json.decode(response.body) as List;
        setState(() {
          _urlHistory = data.map((e) => e.toString()).toList();
        });
      }
    } catch (e) {
      print('Error fetching URL history: $e');
    }
  }

  Future<void> _startTest() async {
    if (_urlController.text.isEmpty || _objectiveController.text.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please enter URL and test objective')),
      );
      return;
    }

    setState(() {
      _isRunning = true;
      _testResult = null;
      _selectedHistoryTest = null;
    });

    try {
      // If a credential is selected, fetch the full credential data
      String? username;
      String? password;
      
      if (_selectedCredId != null) {
        final credResponse = await http.get(
          Uri.parse('${AppConfig.serverUrl}/credentials/$_selectedCredId'),
          headers: {'ngrok-skip-browser-warning': 'true'},
        );
        if (credResponse.statusCode == 200) {
          final credData = json.decode(credResponse.body);
          username = credData['username'];
          password = credData['password'];
        }
      }
      
      final response = await http.post(
        Uri.parse('${AppConfig.serverUrl}/test/start'),
        headers: {
          'Content-Type': 'application/json',
          'ngrok-skip-browser-warning': 'true',
        },
        body: json.encode({
          'url': _urlController.text,
          'objective': _objectiveController.text,
          'username': username,
          'password': password,
        }),
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        _testId = data['test_id'];
        setState(() => _testResult = data); 
        _startPolling();
      } else {
        throw Exception('Failed to start test: ${response.body}');
      }
    } catch (e) {
      setState(() => _isRunning = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error: $e')),
      );
    }
  }

  Future<void> _retryTest(String testId, {bool deeper = false}) async {
    setState(() {
      _isRunning = true;
      _testResult = null;
      _selectedHistoryTest = null;
      _tabController.animateTo(0);
    });
    
    _testId = null; // Clear old ID to avoid immediate status fetch before new one starts

    try {
      final endpoint = deeper ? 'retry-deeper' : 'retry';
      final response = await http.post(
        Uri.parse('${AppConfig.serverUrl}/test/$endpoint/$testId'),
        headers: {
          'Content-Type': 'application/json',
          'ngrok-skip-browser-warning': 'true',
        },
      );
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        _testId = data['test_id'];
        _startPolling();
      } else {
        throw Exception('Failed to retry test');
      }
    } catch (e) {
      setState(() => _isRunning = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error: $e')),
      );
    }
  }

  Future<void> _cancelTest() async {
    if (_testId == null) return;

    try {
      final response = await http.post(
        Uri.parse('${AppConfig.serverUrl}/test/cancel/$_testId'),
        headers: {
          'Content-Type': 'application/json',
          'ngrok-skip-browser-warning': 'true',
        },
      );

      if (response.statusCode == 200) {
        setState(() {
          _isRunning = false;
          _pollTimer?.cancel();
        });
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Test cancelled')),
        );
      }
    } catch (e) {
      print('Error cancelling test: $e');
    }
  }

  void _startPolling() {
    _pollTimer = Timer.periodic(const Duration(seconds: 2), (_) async {
      await _fetchTestStatus();
    });
  }

  Future<void> _fetchTestStatus() async {
    if (_testId == null) return;

    try {
      final response = await http.get(
        Uri.parse('${AppConfig.serverUrl}/test/status/$_testId'),
        headers: {'ngrok-skip-browser-warning': 'true'},
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        setState(() => _testResult = data);

        // Stop polling if test is done
        if (data['status'] != 'running') {
          _pollTimer?.cancel();
          setState(() => _isRunning = false);
        }
      }
    } catch (e) {
      print('Polling error: $e');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('🧪 Tester Agent'),
        backgroundColor: Theme.of(context).colorScheme.inversePrimary,
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(text: 'Runner', icon: Icon(Icons.play_arrow)),
            Tab(text: 'History', icon: Icon(Icons.history)),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildRunnerTab(),
          _buildHistoryTab(),
        ],
      ),
    );
  }

  Widget _buildRunnerTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (_testResult == null) _buildRunnerForm()
          else _buildActiveTestView(),
        ],
      ),
    );
  }

  Widget _buildRunnerForm() {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Column(
      children: [
        // Header
        _buildGlassCard(
          padding: const EdgeInsets.all(16),
          child: Column(
            children: [
              Icon(
                Icons.psychology,
                size: 48,
                color: Colors.deepPurple[300],
              ),
              const SizedBox(height: 8),
              Text(
                'AI-Powered Testing',
                style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                  color: isDark ? Colors.white : Colors.black87,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                'Uses Gemini + Playwright to test your web app',
                style: TextStyle(
                  color: isDark ? Colors.white70 : Colors.grey[600],
                ),
              ),
            ],
          ),
        ),
        
        const SizedBox(height: 16),
        
        // URL Input with Autocomplete
        Autocomplete<String>(
          optionsBuilder: (TextEditingValue textEditingValue) {
            if (textEditingValue.text.isEmpty) {
              return _urlHistory;
            }
            return _urlHistory.where((String option) {
              return option.toLowerCase().contains(textEditingValue.text.toLowerCase());
            });
          },
          onSelected: (String selection) {
            _urlController.text = selection;
          },
          fieldViewBuilder: (context, controller, focusNode, onFieldSubmitted) {
            if (_urlController.text.isNotEmpty && controller.text.isEmpty) {
              controller.text = _urlController.text;
            }
            controller.addListener(() {
              _urlController.text = controller.text;
            });
            
            return TextField(
              controller: controller,
              focusNode: focusNode,
              decoration: InputDecoration(
                labelText: 'URL to Test',
                hintText: 'https://example.com',
                prefixIcon: const Icon(Icons.link),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
              keyboardType: TextInputType.url,
            );
          },
        ),
        
        const SizedBox(height: 16),

        // Repository, Preset, and Credentials Dropdowns
        _buildGlassCard(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Quick Load',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                  color: isDark ? Colors.white : Colors.black87,
                ),
              ),
              const SizedBox(height: 12),
              
              // Repository Dropdown
              _isLoadingRepos
                ? const Center(child: CircularProgressIndicator())
                : DropdownButtonFormField<String>(
                    value: _selectedRepo,
                    decoration: InputDecoration(
                      labelText: 'Repository',
                      prefixIcon: const Icon(Icons.folder_outlined),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                    isExpanded: true,
                    hint: const Text('Select repository'),
                    items: _repos.map((repo) {
                      final fullName = repo['full_name'] ?? '';
                      return DropdownMenuItem<String>(
                        value: fullName,
                        child: Text(fullName, overflow: TextOverflow.ellipsis),
                      );
                    }).toList(),
                    onChanged: (value) {
                      setState(() => _selectedRepo = value);
                      if (value != null) {
                        _loadPresetsAndCreds(value);
                      }
                    },
                  ),
              
              if (_selectedRepo != null && !_isLoadingData) ...[
                const SizedBox(height: 12),
                
                // Test Preset Dropdown
                DropdownButtonFormField<String>(
                  value: _selectedPresetId,
                  decoration: InputDecoration(
                    labelText: 'Test Preset',
                    prefixIcon: const Icon(Icons.science_outlined),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                  isExpanded: true,
                  hint: Text(_presets.isEmpty ? 'No presets saved' : 'Select preset'),
                  items: _presets.map((preset) {
                    return DropdownMenuItem<String>(
                      value: preset['id'],
                      child: Text(preset['title'] ?? 'Untitled', overflow: TextOverflow.ellipsis),
                    );
                  }).toList(),
                  onChanged: _presets.isEmpty ? null : _onPresetSelected,
                ),
                
                const SizedBox(height: 12),
                
                // Credentials Dropdown
                DropdownButtonFormField<String>(
                  value: _selectedCredId,
                  decoration: InputDecoration(
                    labelText: 'Credentials',
                    prefixIcon: const Icon(Icons.lock_outline),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                  isExpanded: true,
                  hint: Text(_creds.isEmpty ? 'No credentials saved' : 'Select credentials'),
                  items: [
                    const DropdownMenuItem<String>(
                      value: null,
                      child: Text('None'),
                    ),
                    ..._creds.map((cred) {
                      return DropdownMenuItem<String>(
                        value: cred['id'],
                        child: Text('${cred['name']} (${cred['username']})', overflow: TextOverflow.ellipsis),
                      );
                    }),
                  ],
                  onChanged: (value) {
                    setState(() => _selectedCredId = value);
                  },
                ),
              ],
              
              if (_isLoadingData)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 12),
                  child: Center(child: CircularProgressIndicator()),
                ),
            ],
          ),
        ),
        
        const SizedBox(height: 16),
        
        // Objective Input
        TextField(
          controller: _objectiveController,
          decoration: InputDecoration(
            labelText: 'Test Objective',
            hintText: 'Verify the login form works correctly',
            prefixIcon: const Icon(Icons.flag),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
            ),
          ),
          maxLines: 3,
        ),
        
        const SizedBox(height: 12),
        
        // Template Chips
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            children: [
              _buildTemplateChip('Verify Login'),
              _buildTemplateChip('Check Search'),
              _buildTemplateChip('Test Checkout'),
              _buildTemplateChip('Homepage Audit'),
              _buildTemplateChip('Contact Form'),
            ],
          ),
        ),
        
        const SizedBox(height: 16),
        
        SizedBox(
          width: double.infinity,
          child: ElevatedButton(
            onPressed: _isRunning ? null : _startTest,
            style: ElevatedButton.styleFrom(
              padding: const EdgeInsets.all(16),
              backgroundColor: Colors.deepPurple,
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            ),
            child: _isRunning
              ? const SizedBox(
                  height: 20,
                  width: 20,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                  ),
                )
              : const Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(Icons.play_arrow),
                    SizedBox(width: 8),
                    Text('Start Test'),
                  ],
                ),
          ),
        ),
      ],
    );
  }

  Widget _buildActiveTestView() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            IconButton(
              icon: const Icon(Icons.arrow_back),
              tooltip: 'Back',
              onPressed: () => setState(() {
                if (!_isRunning) _testResult = null;
              }),
            ),
            const Text('Active Test', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const Spacer(),
            if (_isRunning)
              TextButton.icon(
                onPressed: _cancelTest,
                icon: const Icon(Icons.cancel, color: Colors.red),
                label: const Text('Cancel', style: TextStyle(color: Colors.red)),
              ),
          ],
        ),
        if (_isRunning) ...[
          const SizedBox(height: 8),
          _buildThinkingBubble(_testResult?['thinking'] ?? 'Agent is thinking...'),
        ],
        const SizedBox(height: 16),
        _buildResultCard(_testResult!),
        const SizedBox(height: 24),
        _buildStepsList(_testResult!),
        const SizedBox(height: 100), // Diagnostic spacer
      ],
    );
  }

  Widget _buildThinkingBubble(String text) {
    return _buildGlassCard(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Row(
        children: [
          const SizedBox(
            width: 16,
            height: 16,
            child: CircularProgressIndicator(strokeWidth: 2, color: Colors.deepPurple),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              text,
              style: const TextStyle(
                fontStyle: FontStyle.italic,
                fontSize: 13,
                color: Colors.deepPurple,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHistoryTab() {
    if (_selectedHistoryTest != null) {
      return _buildHistoryDetailView();
    }

    if (_isLoadingHistory) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_allTests.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.history_outlined, size: 64, color: Colors.grey[400]),
            const SizedBox(height: 16),
            const Text('No test history yet', style: TextStyle(color: Colors.grey)),
          ],
        ),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _allTests.length,
      itemBuilder: (context, index) {
        final test = _allTests[index];
        final status = test['status'] ?? 'unknown';
        final isPassed = status == 'passed';
        final isFailed = status == 'failed';
        final date = DateTime.tryParse(test['started_at'] ?? '')?.toLocal();
        final dateStr = date != null ? '${date.day}/${date.month} ${date.hour}:${date.minute}' : 'Recently';

        return Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: _buildGlassCard(
            child: ListTile(
              leading: Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: (isPassed ? Colors.green : (isFailed ? Colors.red : Colors.orange)).withOpacity(0.1),
                  shape: BoxShape.circle,
                ),
                child: Icon(
                  isPassed ? Icons.check : (isFailed ? Icons.close : Icons.hourglass_bottom),
                  color: isPassed ? Colors.green : (isFailed ? Colors.red : Colors.orange),
                  size: 20,
                ),
              ),
              title: Text(
                test['objective'] ?? 'Untitled Test',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontWeight: FontWeight.bold),
              ),
              subtitle: Text(
                '${test['url']} • $dateStr',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontSize: 12),
              ),
              trailing: const Icon(Icons.chevron_right, size: 20),
              onTap: () => setState(() => _selectedHistoryTest = test),
            ),
          ),
        );
      },
    );
  }

  Widget _buildHistoryDetailView() {
    final test = _selectedHistoryTest!;
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              IconButton(
                icon: const Icon(Icons.arrow_back),
                tooltip: 'Back',
                onPressed: () => setState(() => _selectedHistoryTest = null),
              ),
              const Text('Test Details', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
              const Spacer(),
              const SizedBox(width: 8),
            ElevatedButton.icon(
              onPressed: () => _retryTest(_selectedHistoryTest!['test_id'], deeper: true),
              icon: const Icon(Icons.psychology, color: Colors.white),
              label: const Text('Retry (Deeper)', style: TextStyle(color: Colors.white)),
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.deepPurple,
              ),
            ),
              ElevatedButton.icon(
                onPressed: () => _retryTest(test['test_id']),
                icon: const Icon(Icons.refresh, size: 16),
                label: const Text('Retry'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.deepPurple,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(horizontal: 12),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          _buildResultCard(test),
          const SizedBox(height: 24),
          _buildStepsList(test),
        ],
      ),
    );
  }

  Widget _buildResultCard(Map<String, dynamic> result) {
    final status = result['status'];
    final isPassed = status == 'passed';
    final isFailed = status == 'failed';
    final isDark = Theme.of(context).brightness == Brightness.dark;
    
    IconData icon;
    Color color;
    
    if (isPassed) {
      icon = Icons.check_circle;
      color = Colors.green;
    } else if (isFailed) {
      icon = Icons.cancel;
      color = Colors.red;
    } else {
      icon = Icons.hourglass_bottom;
      color = Colors.orange;
    }
    
    return _buildGlassCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          Icon(icon, size: 48, color: color),
          const SizedBox(height: 8),
          Text(
            status.toString().toUpperCase(),
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.bold,
              color: color,
            ),
          ),
          if (result['final_verdict'] != null) ...[
            const SizedBox(height: 8),
            Text(
              result['final_verdict'],
              textAlign: TextAlign.center,
              style: TextStyle(
                color: isDark ? Colors.white70 : Colors.grey[700],
              ),
            ),
          ],
          if (isPassed && result['test_id'] != null) ...[
            const SizedBox(height: 16),
            OutlinedButton.icon(
              onPressed: () => _showSavePresetDialog(result['test_id']),
              icon: const Icon(Icons.bookmark_add_outlined, size: 18),
              label: const Text('Save as Preset'),
              style: OutlinedButton.styleFrom(
                foregroundColor: Colors.deepPurple,
                side: BorderSide(color: Colors.deepPurple[300]!),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Future<void> _showSavePresetDialog(String testId) async {
    final titleController = TextEditingController();
    String? selectedRepo;
    List<Map<String, dynamic>> repos = [];
    bool isLoadingRepos = true;
    bool isSaving = false;
    
    // Fetch repositories
    try {
      final response = await http.get(
        Uri.parse('${AppConfig.serverUrl}/repos'),
        headers: {'ngrok-skip-browser-warning': 'true'},
      );
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        if (data is List) {
          repos = List<Map<String, dynamic>>.from(data);
        } else if (data is Map && data['repos'] is List) {
          repos = List<Map<String, dynamic>>.from(data['repos']);
        }
      }
    } catch (e) {
      print('Error fetching repos: $e');
    }
    isLoadingRepos = false;
    
    final result = await showDialog<bool>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('Save as Preset'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              TextField(
                controller: titleController,
                decoration: const InputDecoration(
                  labelText: 'Preset Title',
                  hintText: 'e.g., Login Flow',
                ),
              ),
              const SizedBox(height: 16),
              const Text('Repository', style: TextStyle(fontSize: 12, color: Colors.grey)),
              const SizedBox(height: 4),
              isLoadingRepos
                ? const Center(child: CircularProgressIndicator())
                : DropdownButtonFormField<String>(
                    value: selectedRepo,
                    decoration: const InputDecoration(
                      border: OutlineInputBorder(),
                      contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                    ),
                    hint: const Text('Select repository'),
                    isExpanded: true,
                    items: repos.map((repo) {
                      final fullName = repo['full_name'] ?? repo['name'] ?? '';
                      return DropdownMenuItem<String>(
                        value: fullName,
                        child: Text(fullName, overflow: TextOverflow.ellipsis),
                      );
                    }).toList(),
                    onChanged: (value) {
                      setDialogState(() => selectedRepo = value);
                    },
                  ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: isSaving ? null : () => Navigator.pop(context, false),
              child: const Text('Cancel'),
            ),
            ElevatedButton(
              onPressed: (selectedRepo == null || isSaving) 
                ? null 
                : () async {
                    setDialogState(() => isSaving = true);
                    try {
                      final response = await http.post(
                        Uri.parse(
                          '${AppConfig.serverUrl}/test/$testId/save-as-preset'
                          '?title=${Uri.encodeComponent(titleController.text)}'
                          '&repo_full_name=${Uri.encodeComponent(selectedRepo!)}'
                        ),
                        headers: {'ngrok-skip-browser-warning': 'true'},
                      );
                      
                      if (response.statusCode == 200) {
                        if (context.mounted) Navigator.pop(context, true);
                      } else {
                        throw Exception('Failed to save preset');
                      }
                    } catch (e) {
                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(content: Text('Error: $e')),
                        );
                        setDialogState(() => isSaving = false);
                      }
                    }
                  },
              child: isSaving
                ? const SizedBox(
                    height: 16,
                    width: 16,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                    ),
                  )
                : const Text('Save'),
            ),
          ],
        ),
      ),
    );
    
    if (result == true) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Preset saved!')),
      );
    }
  }

  Widget _buildStepsList(Map<String, dynamic> result) {
    final steps = (result['steps'] as List?) ?? [];
    if (steps.isEmpty) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Padding(
          padding: EdgeInsets.symmetric(horizontal: 4, vertical: 8),
          child: Text(
            'Test Timeline',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
          ),
        ),
        // Use spread operator with map instead of ListView.builder with shrinkWrap to avoid layout rounding bugs
        ...steps.asMap().entries.map((entry) {
          final index = entry.key;
          final step = entry.value;
          final isLast = index == steps.length - 1;
          final pageState = step['page_state'] ?? 'OTHER';
          final success = step['success'] ?? true;
          final isRunning = result['status'] == 'running' && isLast;

          return Stack(
            children: [
              // Timeline Line (Positioned behind content)
              if (!isLast)
                Positioned(
                  left: 6, // Half of 14 (dot width) - 1 (line width/2)
                  top: 14, // Start after the dot
                  bottom: 0,
                  child: Container(
                    width: 2,
                    color: (success ? Colors.green : Colors.red).withOpacity(0.3),
                  ),
                ),

              // Content Row
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Dot
                  Container(
                    width: 14,
                    height: 14,
                    margin: const EdgeInsets.only(top: 0),
                    decoration: BoxDecoration(
                      color: isRunning ? Colors.blue : (success ? Colors.green : Colors.red),
                      shape: BoxShape.circle,
                      border: Border.all(color: Colors.white, width: 2),
                      boxShadow: isRunning
                        ? [BoxShadow(color: Colors.blue.withOpacity(0.5), blurRadius: 8, spreadRadius: 2)]
                        : null,
                    ),
                    child: isRunning
                      ? const Center(child: Padding(padding: EdgeInsets.all(2), child: CircularProgressIndicator(strokeWidth: 1, color: Colors.white)))
                      : (success
                          ? const Icon(Icons.check, size: 8, color: Colors.white)
                          : const Icon(Icons.close, size: 8, color: Colors.white)),
                  ),
                  const SizedBox(width: 16),
                  // Step Content
                  Expanded(
                    child: Padding(
                      padding: const EdgeInsets.only(bottom: 24),
                      child: _buildGlassCard(
                        padding: const EdgeInsets.all(12),
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Expanded(
                                  child: Text(
                                    step['description'] ?? 'Step ${index + 1}',
                                    style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                                  ),
                                ),
                                const SizedBox(width: 8),
                                _buildPageStateBadge(pageState),
                              ],
                            ),
                            if (step['action'] != null) ...[
                              const SizedBox(height: 8),
                              Container(
                                padding: const EdgeInsets.all(8),
                                decoration: BoxDecoration(
                                  color: Colors.black.withOpacity(0.03),
                                  borderRadius: BorderRadius.circular(8),
                                ),
                                child: Text(
                                  '${step['action']}${step['target'] != null ? ' → ${step['target']}' : ''}',
                                  style: TextStyle(
                                    fontSize: 11,
                                    fontFamily: 'monospace',
                                    color: Theme.of(context).brightness == Brightness.dark
                                      ? Colors.white70
                                      : Colors.grey[700],
                                  ),
                                ),
                              ),
                            ],
                            if (step['reasoning'] != null) ...[
                              const SizedBox(height: 8),
                              Text(
                                step['reasoning'],
                                style: TextStyle(
                                  fontSize: 11,
                                  color: Theme.of(context).brightness == Brightness.dark
                                    ? Colors.white60
                                    : Colors.grey[600],
                                ),
                              ),
                            ],
                            if (step['alternative_selectors'] != null && (step['alternative_selectors'] as List).isNotEmpty) ...[
                              const SizedBox(height: 8),
                              const Text('Alternative Selectors:', style: TextStyle(fontSize: 9, fontWeight: FontWeight.bold)),
                              const SizedBox(height: 4),
                              Wrap(
                                spacing: 4,
                                children: (step['alternative_selectors'] as List).map((s) => Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
                                  decoration: BoxDecoration(
                                    color: Colors.blue.withOpacity(0.05),
                                    borderRadius: BorderRadius.circular(4),
                                    border: Border.all(color: Colors.blue.withOpacity(0.1)),
                                  ),
                                  child: Text(s.toString(), style: const TextStyle(fontSize: 8, fontFamily: 'monospace')),
                                )).toList(),
                              ),
                            ],
                            if (step['debug_info'] != null && (step['debug_info'] as Map).isNotEmpty) ...[
                              const SizedBox(height: 8),
                              const Text('Debug Map:', style: TextStyle(fontSize: 9, fontWeight: FontWeight.bold)),
                              const SizedBox(height: 4),
                              ... (step['debug_info'] as Map).entries.map((e) => Padding(
                                padding: const EdgeInsets.only(bottom: 2),
                                child: Text('• ${e.key}: ${e.value}', style: const TextStyle(fontSize: 8)),
                              )).toList(),
                            ],
                            if (step['error'] != null) ...[
                              const SizedBox(height: 8),
                              Container(
                                padding: const EdgeInsets.all(8),
                                decoration: BoxDecoration(
                                  color: Colors.red.withOpacity(0.1),
                                  borderRadius: BorderRadius.circular(8),
                                ),
                                child: Row(
                                  children: [
                                    const Icon(Icons.error_outline, size: 14, color: Colors.red),
                                    const SizedBox(width: 8),
                                    Expanded(
                                      child: Text(
                                        step['error'],
                                        style: const TextStyle(color: Colors.red, fontSize: 11),
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ],
                            if (step['screenshot'] != null && step['screenshot'].toString().isNotEmpty) ...[
                              const SizedBox(height: 12),
                              ClipRRect(
                                borderRadius: BorderRadius.circular(8),
                                clipBehavior: Clip.antiAlias,
                                child: Image.memory(
                                  base64Decode(step['screenshot']),
                                  height: 148, // Reduced from 150 to avoid rounding overflow
                                  width: double.infinity,
                                  fit: BoxFit.cover,
                                  errorBuilder: (context, error, stackTrace) => const SizedBox.shrink(),
                                ),
                              ),
                            ],
                            const SizedBox(height: 8),
                          ],
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ],
          );
        }),
      ],
    );
  }

  Widget _buildGlassCard({required Widget child, EdgeInsetsGeometry? padding}) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Container(
      decoration: BoxDecoration(
        color: isDark 
          ? Colors.white.withOpacity(0.07) 
          : Colors.white.withOpacity(0.8),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: isDark 
            ? Colors.white.withOpacity(0.12) 
            : Colors.deepPurple.withOpacity(0.15),
          width: 0.5,
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.03),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(16),
        child: Padding(
          padding: padding ?? const EdgeInsets.all(0),
          child: child,
        ),
      ),
    );
  }

  Widget _buildPageStateBadge(String state) {
    final color = _getPageStateColor(state);
    final icon = _getPageStateIcon(state);
    
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withOpacity(0.3), width: 0.5),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 10, color: color),
          const SizedBox(width: 4),
          Text(
            state,
            style: TextStyle(
              fontSize: 9,
              fontWeight: FontWeight.bold,
              color: color,
            ),
          ),
        ],
      ),
    );
  }

  Color _getPageStateColor(String state) {
    switch (state.toUpperCase()) {
      case 'LANDING': return Colors.blue;
      case 'LOGIN': return Colors.green;
      case 'DASHBOARD': return Colors.orange;
      case 'ERROR': return Colors.red;
      case 'SEARCH': return Colors.cyan;
      case 'CHECKOUT': return Colors.purple;
      default: return Colors.grey;
    }
  }

  IconData _getPageStateIcon(String state) {
    switch (state.toUpperCase()) {
      case 'LANDING': return Icons.home;
      case 'LOGIN': return Icons.login;
      case 'DASHBOARD': return Icons.dashboard;
      case 'ERROR': return Icons.error_outline;
      case 'SEARCH': return Icons.search;
      case 'CHECKOUT': return Icons.shopping_cart;
      default: return Icons.insert_drive_file;
    }
  }

  Widget _buildTemplateChip(String label) {
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: ActionChip(
        label: Text(label, style: const TextStyle(fontSize: 12)),
        onPressed: () {
          setState(() {
            _objectiveController.text = 'Verify the $label works correctly and has no errors.';
          });
        },
        backgroundColor: Colors.deepPurple.withOpacity(0.05),
        side: BorderSide(color: Colors.deepPurple.withOpacity(0.1)),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      ),
    );
  }
}
