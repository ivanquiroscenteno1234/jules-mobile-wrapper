import 'package:flutter/material.dart';
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'config.dart';

class CredsScreen extends StatefulWidget {
  const CredsScreen({super.key});

  @override
  State<CredsScreen> createState() => _CredsScreenState();
}

class _CredsScreenState extends State<CredsScreen> {
  List<Map<String, dynamic>> _repos = [];
  List<Map<String, dynamic>> _creds = [];
  String? _selectedRepo;
  bool _isLoadingRepos = true;
  bool _isLoadingCreds = false;

  @override
  void initState() {
    super.initState();
    _loadRepos();
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

  Future<void> _loadCreds(String repoFullName) async {
    setState(() => _isLoadingCreds = true);

    try {
      final parts = repoFullName.split('/');
      if (parts.length != 2) return;

      final response = await http.get(
        Uri.parse(
          '${AppConfig.serverUrl}/repos/${parts[0]}/${parts[1]}/credentials',
        ),
        headers: {'ngrok-skip-browser-warning': 'true'},
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        setState(() {
          if (data is List) {
            _creds = List<Map<String, dynamic>>.from(data);
          } else if (data is Map && data.containsKey('credentials')) {
            _creds = List<Map<String, dynamic>>.from(data['credentials']);
          } else {
            _creds = [];
          }
          _isLoadingCreds = false;
        });
      }
    } catch (e) {
      print('Error loading credentials: $e');
      setState(() => _isLoadingCreds = false);
    }
  }

  Future<void> _addCred() async {
    if (_selectedRepo == null) return;

    final nameController = TextEditingController();
    final usernameController = TextEditingController();
    final passwordController = TextEditingController();
    bool obscurePassword = true;

    final result = await showDialog<bool>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('Add Credential'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: nameController,
                  onChanged: (_) => setDialogState(() {}),
                  decoration: const InputDecoration(
                    labelText: 'Name',
                    hintText: 'e.g., Admin Account',
                    prefixIcon: Icon(Icons.label_outline),
                  ),
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: usernameController,
                  onChanged: (_) => setDialogState(() {}),
                  decoration: const InputDecoration(
                    labelText: 'Username / Email',
                    hintText: 'e.g., admin@example.com',
                    prefixIcon: Icon(Icons.person_outline),
                  ),
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: passwordController,
                  obscureText: obscurePassword,
                  onChanged: (_) => setDialogState(() {}),
                  decoration: InputDecoration(
                    labelText: 'Password',
                    prefixIcon: const Icon(Icons.lock_outline),
                    suffixIcon: IconButton(
                      icon: Icon(
                        obscurePassword
                            ? Icons.visibility
                            : Icons.visibility_off,
                      ),
                      tooltip: obscurePassword
                          ? 'Show Password'
                          : 'Hide Password',
                      onPressed: () => setDialogState(
                        () => obscurePassword = !obscurePassword,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancel'),
            ),
            Tooltip(
              message:
                  (nameController.text.isEmpty ||
                      usernameController.text.isEmpty ||
                      passwordController.text.isEmpty)
                  ? 'Please fill all fields'
                  : 'Save credential',
              child: ElevatedButton(
                onPressed:
                    (nameController.text.isEmpty ||
                        usernameController.text.isEmpty ||
                        passwordController.text.isEmpty)
                    ? null
                    : () => Navigator.pop(context, true),
                child: const Text('Save'),
              ),
            ),
          ],
        ),
      ),
    );

    if (result == true &&
        nameController.text.isNotEmpty &&
        usernameController.text.isNotEmpty &&
        passwordController.text.isNotEmpty) {
      try {
        final parts = _selectedRepo!.split('/');
        final response = await http.post(
          Uri.parse(
            '${AppConfig.serverUrl}/repos/${parts[0]}/${parts[1]}/credentials',
          ),
          headers: {
            'ngrok-skip-browser-warning': 'true',
            'Content-Type': 'application/json',
          },
          body: json.encode({
            'name': nameController.text,
            'username': usernameController.text,
            'password': passwordController.text,
          }),
        );

        if (response.statusCode == 200) {
          ScaffoldMessenger.of(
            context,
          ).showSnackBar(const SnackBar(content: Text('Credential saved!')));
          _loadCreds(_selectedRepo!);
        } else {
          throw Exception('Failed to save credential');
        }
      } catch (e) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red),
        );
      }
    }
  }

  Future<void> _deleteCred(String credId) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Credential'),
        content: const Text('Are you sure you want to delete this credential?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            child: const Text('Delete'),
          ),
        ],
      ),
    );

    if (confirm == true) {
      try {
        final response = await http.delete(
          Uri.parse('${AppConfig.serverUrl}/credentials/$credId'),
          headers: {'ngrok-skip-browser-warning': 'true'},
        );

        if (response.statusCode == 200) {
          ScaffoldMessenger.of(
            context,
          ).showSnackBar(const SnackBar(content: Text('Credential deleted')));
          _loadCreds(_selectedRepo!);
        }
      } catch (e) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Manage Credentials'),
        backgroundColor: isDark ? Colors.grey[900] : Colors.deepPurple,
        foregroundColor: Colors.white,
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Repository Dropdown
            _buildGlassCard(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Repository',
                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                  ),
                  const SizedBox(height: 12),
                  _isLoadingRepos
                      ? const Center(child: CircularProgressIndicator())
                      : DropdownButtonFormField<String>(
                          value: _selectedRepo,
                          decoration: InputDecoration(
                            prefixIcon: const Icon(Icons.folder_outlined),
                            border: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(12),
                            ),
                            hintText: 'Select a repository',
                          ),
                          isExpanded: true,
                          items: _repos.map((repo) {
                            final fullName = repo['full_name'] ?? '';
                            return DropdownMenuItem<String>(
                              value: fullName,
                              child: Text(
                                fullName,
                                overflow: TextOverflow.ellipsis,
                              ),
                            );
                          }).toList(),
                          onChanged: (value) {
                            setState(() => _selectedRepo = value);
                            if (value != null) {
                              _loadCreds(value);
                            }
                          },
                        ),
                ],
              ),
            ),
            const SizedBox(height: 16),

            // Credentials List
            Expanded(
              child: _buildGlassCard(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          'Saved Credentials (${_creds.length})',
                          style: const TextStyle(
                            fontWeight: FontWeight.bold,
                            fontSize: 16,
                          ),
                        ),
                        if (_selectedRepo != null)
                          ElevatedButton.icon(
                            onPressed: _addCred,
                            icon: const Icon(Icons.add),
                            label: const Text('Add'),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: Colors.deepPurple,
                              foregroundColor: Colors.white,
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(12),
                              ),
                            ),
                          ),
                      ],
                    ),
                    const SizedBox(height: 16),

                    if (_selectedRepo == null)
                      const Expanded(
                        child: Center(
                          child: Text(
                            'Select a repository to view credentials',
                            style: TextStyle(color: Colors.grey),
                          ),
                        ),
                      )
                    else if (_isLoadingCreds)
                      const Expanded(
                        child: Center(child: CircularProgressIndicator()),
                      )
                    else if (_creds.isEmpty)
                      const Expanded(
                        child: Center(
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(
                                Icons.lock_outline,
                                size: 48,
                                color: Colors.grey,
                              ),
                              SizedBox(height: 12),
                              Text(
                                'No credentials saved',
                                style: TextStyle(color: Colors.grey),
                              ),
                            ],
                          ),
                        ),
                      )
                    else
                      Expanded(
                        child: ListView.separated(
                          itemCount: _creds.length,
                          separatorBuilder: (context, index) =>
                              const Divider(height: 1),
                          itemBuilder: (context, index) {
                            final cred = _creds[index];
                            return ListTile(
                              contentPadding: const EdgeInsets.symmetric(
                                vertical: 4,
                              ),
                              leading: Container(
                                padding: const EdgeInsets.all(8),
                                decoration: BoxDecoration(
                                  color: Colors.deepPurple.withOpacity(0.1),
                                  borderRadius: BorderRadius.circular(12),
                                ),
                                child: const Icon(
                                  Icons.person,
                                  color: Colors.deepPurple,
                                  size: 20,
                                ),
                              ),
                              title: Text(
                                cred['name'] ?? 'Unnamed',
                                style: const TextStyle(
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                              subtitle: Text(
                                cred['username'] ?? '',
                                style: TextStyle(
                                  color: isDark
                                      ? Colors.white60
                                      : Colors.grey[600],
                                ),
                              ),
                              trailing: IconButton(
                                icon: const Icon(
                                  Icons.delete_outline,
                                  color: Colors.red,
                                ),
                                tooltip: 'Delete Credential',
                                onPressed: () => _deleteCred(cred['id']),
                              ),
                            );
                          },
                        ),
                      ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
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
}
