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

class _TestScreenState extends State<TestScreen> {
  final _urlController = TextEditingController();
  final _objectiveController = TextEditingController();
  final _usernameController = TextEditingController();
  final _passwordController = TextEditingController();
  
  bool _isRunning = false;
  String? _testId;
  Map<String, dynamic>? _testResult;
  Timer? _pollTimer;
  List<String> _urlHistory = [];

  @override
  void initState() {
    super.initState();
    _fetchUrlHistory();
  }

  @override
  void dispose() {
    _urlController.dispose();
    _objectiveController.dispose();
    _usernameController.dispose();
    _passwordController.dispose();
    _pollTimer?.cancel();
    super.dispose();
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
    });

    try {
      final response = await http.post(
        Uri.parse('${AppConfig.serverUrl}/test/start'),
        headers: {
          'Content-Type': 'application/json',
          'ngrok-skip-browser-warning': 'true',
        },
        body: json.encode({
          'url': _urlController.text,
          'objective': _objectiveController.text,
          'username': _usernameController.text.isNotEmpty ? _usernameController.text : null,
          'password': _passwordController.text.isNotEmpty ? _passwordController.text : null,
        }),
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        _testId = data['test_id'];
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
    final isDark = Theme.of(context).brightness == Brightness.dark;
    
    return Scaffold(
      appBar: AppBar(
        title: const Text('🧪 Tester Agent'),
        backgroundColor: Theme.of(context).colorScheme.inversePrimary,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Header
            Card(
              child: Padding(
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
                    const SizedBox(height: 16),
                    const Divider(),
                    const SizedBox(height: 16),
                    if (kIsWeb) ...[
                      const SizedBox(height: 8),
                      Text(
                        'Note: On web, notifications are logged to the browser console.',
                        style: TextStyle(
                          fontSize: 11,
                          fontStyle: FontStyle.italic,
                          color: isDark ? Colors.white54 : Colors.grey[600],
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ),
            
            const SizedBox(height: 16),
            
            // URL Input
            // URL Input with Autocomplete
            Autocomplete<String>(
              optionsBuilder: (TextEditingValue textEditingValue) {
                // Show all URLs when empty (on focus), or filter when typing
                if (textEditingValue.text.isEmpty) {
                  return _urlHistory;  // Show all suggestions on focus
                }
                return _urlHistory.where((String option) {
                  return option.toLowerCase().contains(textEditingValue.text.toLowerCase());
                });
              },
              onSelected: (String selection) {
                _urlController.text = selection;
              },
              fieldViewBuilder: (context, controller, focusNode, onFieldSubmitted) {
                // Sync internal controller with autocomplete controller
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
                      borderRadius: BorderRadius.circular(8),
                    ),
                  ),
                  keyboardType: TextInputType.url,
                );
              },
            ),
            
            const SizedBox(height: 16),

            // Credentials Section
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _usernameController,
                    decoration: InputDecoration(
                      labelText: 'Username (Optional)',
                      hintText: 'admin',
                      prefixIcon: const Icon(Icons.person_outline),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(8),
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: TextField(
                    controller: _passwordController,
                    obscureText: true,
                    decoration: InputDecoration(
                      labelText: 'Password (Optional)',
                      hintText: '••••••••',
                      prefixIcon: const Icon(Icons.lock_outline),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(8),
                      ),
                    ),
                  ),
                ),
              ],
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
                  borderRadius: BorderRadius.circular(8),
                ),
              ),
              maxLines: 3,
            ),
            
            const SizedBox(height: 16),
            
            // Start Button
            ElevatedButton.icon(
              onPressed: _isRunning ? null : _startTest,
              icon: _isRunning 
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.play_arrow),
              label: Text(_isRunning ? 'Testing...' : 'Start Test'),
              style: ElevatedButton.styleFrom(
                padding: const EdgeInsets.all(16),
                backgroundColor: Colors.deepPurple,
                foregroundColor: Colors.white,
              ),
            ),
            
            const SizedBox(height: 24),
            
            // Results
            if (_testResult != null) ...[
              _buildResultCard(),
              const SizedBox(height: 16),
              _buildStepsList(),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildResultCard() {
    final status = _testResult!['status'];
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
    
    return Card(
      color: color.withOpacity(0.1),
      child: Padding(
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
            if (_testResult!['final_verdict'] != null) ...[
              const SizedBox(height: 8),
              Text(
                _testResult!['final_verdict'],
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: isDark ? Colors.white70 : Colors.grey[700],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildStepsList() {
    final steps = _testResult!['steps'] as List? ?? [];
    final isDark = Theme.of(context).brightness == Brightness.dark;
    
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Test Steps (${steps.length})',
          style: TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.bold,
            color: isDark ? Colors.white : Colors.black87,
          ),
        ),
        const SizedBox(height: 8),
        ListView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          itemCount: steps.length,
          itemBuilder: (context, index) {
            final step = steps[index];
            final success = step['success'] ?? true;
            
            return Card(
              margin: const EdgeInsets.only(bottom: 8),
              child: ListTile(
                leading: CircleAvatar(
                  backgroundColor: success ? Colors.green : Colors.red,
                  child: Text(
                    '${index + 1}',
                    style: const TextStyle(color: Colors.white, fontSize: 12),
                  ),
                ),
                title: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (step['page_state'] != null)
                      Container(
                        margin: const EdgeInsets.only(bottom: 4),
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: Colors.deepPurple.withOpacity(0.1),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                          step['page_state'].toString(),
                          style: const TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.bold,
                            color: Colors.deepPurple,
                          ),
                        ),
                      ),
                    Text(
                      // Show natural language description if available, otherwise show action
                      step['description'] != null && step['description'].toString().isNotEmpty
                          ? step['description'].toString()
                          : '${step['action']}${step['target'] != null ? ' → ${step['target']}' : ''}',
                      style: TextStyle(
                        fontWeight: FontWeight.w500,
                        color: isDark ? Colors.white : Colors.black87,
                      ),
                    ),
                  ],
                ),
                subtitle: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Show technical details if description exists
                    if (step['description'] != null && step['description'].toString().isNotEmpty)
                      Text(
                        '${step['action']}${step['target'] != null ? ' → ${step['target']}' : ''}',
                        style: TextStyle(
                          fontSize: 11,
                          fontStyle: FontStyle.italic,
                          color: isDark ? Colors.white54 : Colors.grey,
                        ),
                      ),
                    if (step['reasoning'] != null && step['reasoning'].toString().isNotEmpty)
                      Text(
                        step['reasoning'],
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          color: isDark ? Colors.white70 : Colors.grey[600],
                        ),
                      ),
                  ],
                ),
              ),
            );
          },
        ),
      ],
    );
  }
}
