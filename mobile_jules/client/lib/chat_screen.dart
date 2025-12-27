import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:http/http.dart' as http;
import 'config.dart';

class ChatMessage {
  final String id;
  final String content;
  final String originator;
  final String? timestamp;
  final String type;
  final String? planId;
  final List<dynamic>? steps;
  final String? title;
  final String? description;
  final String? pullRequestUrl;
  final String? julesUrl;
  final String? repoName;
  final bool? isWaiting;
  final bool? hasPatch;
  final String? sessionId;
  final List<Map<String, dynamic>>? artifacts;

  ChatMessage({
    required this.id,
    required this.content,
    this.originator = 'agent',
    this.timestamp,
    this.type = 'message',
    this.planId,
    this.steps,
    this.title,
    this.description,
    this.pullRequestUrl,
    this.julesUrl,
    this.repoName,
    this.isWaiting,
    this.hasPatch,
    this.sessionId,
    this.artifacts,
  });

  factory ChatMessage.fromJson(Map<String, dynamic> json) {
    return ChatMessage(
      id: json['id'] ?? DateTime.now().millisecondsSinceEpoch.toString(),
      content: json['content'] ?? json['message'] ?? '',
      originator: json['originator'] ?? 'agent',
      timestamp: json['timestamp'],
      type: json['type'] ?? 'message',
      planId: json['planId'],
      steps: json['steps'],
      title: json['title'],
      description: json['description'],
      pullRequestUrl: json['pullRequestUrl'],
      julesUrl: json['julesUrl'],
      repoName: json['repoName'],
      isWaiting: json['isWaiting'],
      hasPatch: json['hasPatch'],
      sessionId: json['sessionId'],
      artifacts: json['artifacts'] != null ? List<Map<String, dynamic>>.from(json['artifacts']) : null,
    );
  }

  factory ChatMessage.user(String text) {
    return ChatMessage(
      id: 'user_${DateTime.now().millisecondsSinceEpoch}',
      type: 'user',
      originator: 'user',
      content: text,
    );
  }
}

class PlanStep {
  final String id;
  final String title;
  final int index;

  PlanStep({required this.id, required this.title, required this.index});

  factory PlanStep.fromJson(Map<String, dynamic> json) {
    return PlanStep(
      id: json['id'] ?? '',
      title: json['title'] ?? '',
      index: json['index'] ?? 0,
    );
  }
}

class ChatScreen extends StatefulWidget {
  final String repoName;
  final String sourceId;
  final String? sessionId; // Optional for reconnecting

  const ChatScreen({
    super.key, 
    required this.repoName, 
    required this.sourceId,
    this.sessionId,
  });

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final TextEditingController _controller = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  late WebSocketChannel _channel;
  final List<ChatMessage> _messages = [];
  bool _isConnected = false;
  bool _isWaiting = false; // Start as false - button should be enabled for new sessions
  String? _currentSessionId;
  String? _pendingPlanId;
  
  // Publish state tracking
  bool _isPublishing = false;
  String? _publishStatus; // 'success', 'error', or null
  String? _publishMessage; // Success/error message
  String? _createdPrUrl; // URL of the created PR
  String? _createdBranchUrl; // URL of the created branch
  
  // Branch selection
  List<String> _availableBranches = [];
  String _selectedBranch = 'main';
  bool _isLoadingBranches = false;
  
  // Session state tracking
  String _sessionState = 'UNKNOWN'; // QUEUED, PLANNING, AWAITING_PLAN_APPROVAL, IN_PROGRESS, COMPLETED, FAILED

  @override
  void initState() {
    super.initState();
    _connect();
  }

  void _connect() {
    final wsUrl = AppConfig.serverUrl.replaceFirst('http', 'ws');
    String uri = '$wsUrl/chat/${widget.sourceId}';
    
    // Build query parameters
    final queryParams = <String, String>{};
    
    if (widget.sessionId != null) {
      queryParams['session_id'] = widget.sessionId!;
    }
    
    // Pass auto_mode setting
    if (AppConfig.autoMode) {
      queryParams['auto_mode'] = 'true';
    }
    
    if (queryParams.isNotEmpty) {
      uri += '?${queryParams.entries.map((e) => '${e.key}=${Uri.encodeComponent(e.value)}').join('&')}';
    }
    
    try {
      _channel = WebSocketChannel.connect(Uri.parse(uri));
      _isConnected = true;
      
      _channel.stream.listen(
        (message) {
          try {
            final json = jsonDecode(message);
            final chatMsg = ChatMessage.fromJson(json);
            
            setState(() {
              // Prevent duplicate messages by checking ID
              final isDuplicate = _messages.any((m) => m.id == chatMsg.id);
              if (!isDuplicate) {
                _messages.add(chatMsg);
              }
              
              // Track session ID
              if (json['sessionId'] != null) {
                _currentSessionId = json['sessionId'];
              }
              
              // Track session state
              if (json['sessionState'] != null) {
                _sessionState = json['sessionState'];
              }
              // Infer state from message types
              if (chatMsg.type == 'plan') {
                _sessionState = 'AWAITING_PLAN_APPROVAL';
              } else if (chatMsg.type == 'progress' || chatMsg.type == 'artifact') {
                _sessionState = 'IN_PROGRESS';
              } else if (chatMsg.type == 'completed') {
                _sessionState = 'COMPLETED';
              } else if (chatMsg.type == 'failed') {
                _sessionState = 'FAILED';
              }
              // Track pending plan for approval
              if (chatMsg.type == 'plan' && chatMsg.planId != null) {
                _pendingPlanId = chatMsg.planId;
              }
              
              // Clear pending plan if session is completed
              if (chatMsg.type == 'completed') {
                _pendingPlanId = null;
              }
              
              // Only stop waiting on completion events or when Jules needs input
              // Keep waiting for: progress, status, artifact messages
              if (chatMsg.type == 'completed' || 
                  chatMsg.type == 'plan' ||
                  chatMsg.type == 'message') {
                _isWaiting = false;
              }
            });
            _scrollToBottom();
          } catch (e) {
            // Fallback for non-JSON messages (legacy)
            setState(() {
              _messages.add(ChatMessage(
                id: DateTime.now().millisecondsSinceEpoch.toString(),
                type: 'message',
                content: message.toString(),
              ));
              _isWaiting = false;
            });
            _scrollToBottom();
          }
        },
        onError: (error) {
          setState(() {
            _messages.add(ChatMessage(
              id: 'error',
              type: 'system',
              content: 'Connection Error: $error',
            ));
            _isConnected = false;
            _isWaiting = false;
          });
        },
        onDone: () {
          setState(() {
            _messages.add(ChatMessage(
              id: 'disconnected',
              type: 'system',
              content: 'Disconnected.',
            ));
            _isConnected = false;
            _isWaiting = false;
          });
        },
      );
    } catch (e) {
      setState(() {
        _messages.add(ChatMessage(
          id: 'error',
          type: 'system',
          content: 'Could not connect: $e',
        ));
        _isConnected = false;
        _isWaiting = false;
      });
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  void dispose() {
    if (_isConnected) {
      _channel.sink.close();
    }
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _sendMessage() {
    if (_controller.text.isNotEmpty && _isConnected) {
      final text = _controller.text;
      
      setState(() {
        _messages.add(ChatMessage.user(text));
        _isWaiting = true;
      });
      
      _channel.sink.add(text);
      _controller.clear();
      _scrollToBottom();
    }
  }

  void _approvePlan() {
    if (_isConnected) {
      _channel.sink.add('/approve');
      setState(() {
        _pendingPlanId = null;
        _isWaiting = true;  // Show working indicator after approval
      });
    }
  }

  Future<void> _fetchBranches(String owner, String repo) async {
    if (_isLoadingBranches) return;
    
    setState(() {
      _isLoadingBranches = true;
    });
    
    try {
      final response = await http.get(
        Uri.parse('${AppConfig.serverUrl}/repos/$owner/$repo/branches'),
        headers: {'ngrok-skip-browser-warning': 'true'},
      );
      
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        final branches = (data['branches'] as List)
            .map((b) => b['name'] as String)
            .toList();
        
        setState(() {
          _availableBranches = branches;
          _isLoadingBranches = false;
          // Set default to main or first branch
          if (branches.contains('main')) {
            _selectedBranch = 'main';
          } else if (branches.contains('master')) {
            _selectedBranch = 'master';
          } else if (branches.isNotEmpty) {
            _selectedBranch = branches.first;
          }
        });
      } else {
        setState(() {
          _isLoadingBranches = false;
        });
      }
    } catch (e) {
      print('Error fetching branches: $e');
      setState(() {
        _isLoadingBranches = false;
      });
    }
  }

  Future<void> _createGitHubPR(String sessionId, {bool branchOnly = false}) async {
    setState(() {
      _isPublishing = true;
      _publishStatus = null;
      _publishMessage = null;
    });
    
    try {
      final uri = Uri.parse('${AppConfig.serverUrl}/sessions/${Uri.encodeComponent(sessionId)}/github-pr')
          .replace(queryParameters: {
            'base_branch': _selectedBranch,
            'branch_only': branchOnly.toString(),
          });
      
      final response = await http.post(
        uri,
        headers: {'ngrok-skip-browser-warning': 'true'},
      );
      
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        
        if (data['type'] == 'branch') {
          // Branch only created
          setState(() {
            _isPublishing = false;
            _publishStatus = 'success';
            _publishMessage = 'Branch "${data['branch']}" created!';
            _createdBranchUrl = data['branch_url'];
          });
        } else {
          // PR created
          setState(() {
            _isPublishing = false;
            _publishStatus = 'success';
            _publishMessage = 'PR #${data['pr_number']} created!';
            _createdPrUrl = data['pr_url'];
          });
        }
      } else {
        final errorData = json.decode(response.body);
        setState(() {
          _isPublishing = false;
          _publishStatus = 'error';
          _publishMessage = errorData['detail'] ?? 'Failed to create PR';
        });
      }
    } catch (e) {
      setState(() {
        _isPublishing = false;
        _publishStatus = 'error';
        _publishMessage = 'Error: $e';
      });
    }
  }

  Future<void> _copyPatch(String sessionId) async {
    try {
      final response = await http.get(
        Uri.parse('${AppConfig.serverUrl}/sessions/$sessionId/patch'),
        headers: {'ngrok-skip-browser-warning': 'true'},
      );
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final patchContent = data['instructions'] ?? data['patch'] ?? '';
        
        await Clipboard.setData(ClipboardData(text: patchContent));
        
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Patch copied to clipboard! Use \'git apply patch.diff\' to apply.'),
              duration: Duration(seconds: 3),
            ),
          );
        }
      } else {
        throw Exception('Patch not found');
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error copying patch: $e')),
        );
      }
    }
  }

  Widget _buildSessionStateBadge() {
    Color bgColor;
    Color textColor = Colors.white;
    String label;
    
    switch (_sessionState) {
      case 'QUEUED':
        bgColor = Colors.grey;
        label = 'Queued';
        break;
      case 'PLANNING':
        bgColor = Colors.orange;
        label = 'Planning';
        break;
      case 'AWAITING_PLAN_APPROVAL':
        bgColor = Colors.amber;
        textColor = Colors.black87;
        label = 'Awaiting Approval';
        break;
      case 'AWAITING_USER_FEEDBACK':
        bgColor = Colors.purple;
        label = 'Needs Input';
        break;
      case 'IN_PROGRESS':
        bgColor = Colors.blue;
        label = 'Working';
        break;
      case 'PAUSED':
        bgColor = Colors.grey.shade600;
        label = 'Paused';
        break;
      case 'COMPLETED':
        bgColor = Colors.green;
        label = 'Completed';
        break;
      case 'FAILED':
        bgColor = Colors.red;
        label = 'Failed';
        break;
      default:
        bgColor = Colors.grey.shade400;
        label = _isConnected ? 'Connected' : 'Connecting...';
    }
    
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: textColor,
          fontSize: 12,
          fontWeight: FontWeight.w500,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            Expanded(child: Text(widget.repoName)),
            _buildSessionStateBadge(),
          ],
        ),
        backgroundColor: Theme.of(context).colorScheme.inversePrimary,
      ),
      body: Column(
        children: [
          Expanded(
            child: ListView.builder(
              controller: _scrollController,
              padding: const EdgeInsets.all(16),
              itemCount: _messages.length + (_isWaiting ? 1 : 0),
              itemBuilder: (context, index) {
                if (_isWaiting && index == _messages.length) {
                  return _buildWorkingIndicator();
                }
                return _buildMessageWidget(_messages[index]);
              },
            ),
          ),
          // Show approve button if there's a pending plan
          if (_pendingPlanId != null)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              color: Colors.amber[50],
              child: Row(
                children: [
                  const Icon(Icons.check_circle_outline, color: Colors.amber),
                  const SizedBox(width: 8),
                  const Expanded(child: Text('Plan ready for approval')),
                  ElevatedButton(
                    onPressed: _approvePlan,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.green,
                      foregroundColor: Colors.white,
                    ),
                    child: const Text('Approve'),
                  ),
                ],
              ),
            ),
          // Task Templates Row
          if (_messages.isEmpty || _messages.length <= 2)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              child: SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: Row(
                  children: [
                    _buildTemplateChip('🐛 Fix bug', 'Fix a bug in '),
                    _buildTemplateChip('✨ Add feature', 'Add a new feature: '),
                    _buildTemplateChip('🧪 Add tests', 'Add unit tests for '),
                    _buildTemplateChip('📝 Add docs', 'Add documentation for '),
                    _buildTemplateChip('♻️ Refactor', 'Refactor the '),
                    _buildTemplateChip('🔧 Configure', 'Update the configuration for '),
                  ],
                ),
              ),
            ),
          Padding(
            padding: const EdgeInsets.all(8.0),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _controller,
                    decoration: const InputDecoration(
                      hintText: 'Ask Jules something...',
                      border: OutlineInputBorder(),
                    ),
                    onSubmitted: (_) => _sendMessage(),
                  ),
                ),
                const SizedBox(width: 8),
                IconButton(
                  icon: const Icon(Icons.send),
                  color: Colors.deepPurple,
                  onPressed: _isWaiting ? null : _sendMessage,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTemplateChip(String label, String prefix) {
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: ActionChip(
        label: Text(
          label, 
          style: const TextStyle(
            fontSize: 12, 
            color: Colors.black87,  // Dark text for visibility
            fontWeight: FontWeight.w500,
          ),
        ),
        onPressed: () {
          setState(() {
            _controller.text = prefix;
            _controller.selection = TextSelection.fromPosition(
              TextPosition(offset: _controller.text.length),
            );
          });
        },
        backgroundColor: Colors.amber[100],  // Bright yellow background
        side: BorderSide(color: Colors.amber[300]!),
      ),
    );
  }

  Widget _buildMessageWidget(ChatMessage msg) {
    print('DEBUG _buildMessageWidget: type=${msg.type}, content=${msg.content.substring(0, msg.content.length > 50 ? 50 : msg.content.length)}');
    switch (msg.type) {
      case 'plan':
        return _buildPlanCard(msg);
      case 'progress':
        return _buildProgressCard(msg);
      case 'completed':
        return _buildCompletedBadge(msg);
      case 'status':
        return _buildStatusBadge(msg);
      case 'artifact':
        return _buildJulesBubble(msg);  // Show artifacts as regular bubbles
      case 'user':
        return _buildUserBubble(msg);
      case 'system':
        return _buildSystemBubble(msg);
      default:
        // Skip empty messages
        if (msg.content.isEmpty) {
          return const SizedBox.shrink();
        }
        return _buildJulesBubble(msg);
    }
  }

  Widget _buildPlanCard(ChatMessage msg) {
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 8),
      child: ExpansionTile(
        leading: const Icon(Icons.list_alt, color: Colors.deepPurple),
        title: Text('Plan (${msg.steps?.length ?? 0} steps)'),
        children: msg.steps?.asMap().entries.map((entry) {
          final idx = entry.key;
          final step = entry.value as Map<String, dynamic>;
          return ListTile(
            leading: CircleAvatar(
              radius: 12,
              backgroundColor: Colors.deepPurple,
              child: Text(
                '${idx + 1}',
                style: const TextStyle(color: Colors.white, fontSize: 12),
              ),
            ),
            title: Text(step['title'] ?? 'Step ${idx + 1}'),
          );
        }).toList() ?? [],
      ),
    );
  }

  Widget _buildProgressCard(ChatMessage msg) {
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 4),
      color: Colors.blue[50],
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ListTile(
            leading: const Icon(Icons.play_circle_outline, color: Colors.blue),
            title: Text(msg.title ?? msg.content),
            subtitle: msg.description != null ? Text(msg.description!) : null,
          ),
          // Show artifacts if present
          if (msg.artifacts != null && msg.artifacts!.isNotEmpty)
            ...msg.artifacts!.map((art) => _buildArtifactWidget(art)).toList(),
        ],
      ),
    );
  }

  Widget _buildArtifactWidget(Map<String, dynamic> artifact) {
    final type = artifact['type'];
    
    switch (type) {
      case 'file_change':
        return _buildFileChangeBadge(artifact);
      case 'bash':
        return _buildBashOutputCard(artifact);
      case 'media':
        return _buildMediaBadge(artifact);
      default:
        return const SizedBox.shrink();
    }
  }

  Widget _buildFileChangeBadge(Map<String, dynamic> artifact) {
    final commitMsg = artifact['commitMsg'] ?? '';
    final patch = artifact['patch'] ?? '';
    
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 0, 16, 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // File change badge
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color: Colors.green[100],
              borderRadius: BorderRadius.circular(4),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.edit_document, size: 16, color: Colors.green),
                const SizedBox(width: 4),
                const Text('File Changed', style: TextStyle(fontSize: 12, color: Colors.green)),
              ],
            ),
          ),
          // Show commit message if present
          if (commitMsg.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(
                commitMsg,
                style: TextStyle(fontSize: 12, color: Colors.grey[600]),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ),
          // Show diff preview if present
          if (patch.isNotEmpty)
            _buildDiffPreview(patch),
        ],
      ),
    );
  }

  Widget _buildDiffPreview(String patch) {
    if (patch.isEmpty) return const SizedBox.shrink();
    
    // Parse diff and show first few lines
    final lines = patch.split('\n').take(10).toList();
    
    return Container(
      margin: const EdgeInsets.only(top: 8),
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: Colors.grey[900],
        borderRadius: BorderRadius.circular(4),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.code, size: 14, color: Colors.white70),
              const SizedBox(width: 4),
              const Text('Diff', style: TextStyle(color: Colors.white70, fontSize: 12)),
              const Spacer(),
              GestureDetector(
                onTap: () => _showFullDiff(patch),
                child: const Text('View Full', style: TextStyle(color: Colors.blue, fontSize: 12)),
              ),
            ],
          ),
          const SizedBox(height: 4),
          ...lines.map((line) => _buildDiffLine(line)).toList(),
          if (patch.split('\n').length > 10)
            const Text('...', style: TextStyle(color: Colors.white54)),
        ],
      ),
    );
  }

  Widget _buildDiffLine(String line) {
    Color color = Colors.white70;
    if (line.startsWith('+') && !line.startsWith('+++')) {
      color = Colors.greenAccent;
    } else if (line.startsWith('-') && !line.startsWith('---')) {
      color = Colors.redAccent;
    } else if (line.startsWith('@@')) {
      color = Colors.cyanAccent;
    }
    
    return Text(
      line,
      style: TextStyle(
        fontFamily: 'monospace',
        fontSize: 11,
        color: color,
      ),
      maxLines: 1,
      overflow: TextOverflow.ellipsis,
    );
  }

  void _showFullDiff(String patch) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.grey[900],
      builder: (context) => DraggableScrollableSheet(
        initialChildSize: 0.7,
        minChildSize: 0.5,
        maxChildSize: 0.95,
        expand: false,
        builder: (context, scrollController) => Column(
          children: [
            Container(
              padding: const EdgeInsets.all(16),
              child: Row(
                children: [
                  const Icon(Icons.code, color: Colors.white),
                  const SizedBox(width: 8),
                  const Text('Code Changes', style: TextStyle(color: Colors.white, fontSize: 18)),
                  const Spacer(),
                  IconButton(
                    icon: const Icon(Icons.close, color: Colors.white),
                    onPressed: () => Navigator.pop(context),
                  ),
                ],
              ),
            ),
            Expanded(
              child: ListView(
                controller: scrollController,
                padding: const EdgeInsets.all(16),
                children: patch.split('\n').map((line) => _buildDiffLine(line)).toList(),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildBashOutputCard(Map<String, dynamic> artifact) {
    final command = artifact['command'] ?? '';
    final output = artifact['output'] ?? '';
    final exitCode = artifact['exitCode'];
    
    if (command.isEmpty && output.isEmpty) return const SizedBox.shrink();
    
    final isSuccess = exitCode == null || exitCode == 0;
    
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 0, 16, 12),
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: Colors.grey[850],
        borderRadius: BorderRadius.circular(4),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (command.isNotEmpty)
            Row(
              children: [
                const Icon(Icons.terminal, size: 14, color: Colors.greenAccent),
                const SizedBox(width: 4),
                Expanded(
                  child: Text(
                    command,
                    style: const TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 12,
                      color: Colors.greenAccent,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                // Exit code badge
                if (exitCode != null)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      color: isSuccess ? Colors.green.withOpacity(0.2) : Colors.red.withOpacity(0.2),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          isSuccess ? Icons.check_circle : Icons.error,
                          size: 12,
                          color: isSuccess ? Colors.green : Colors.red,
                        ),
                        const SizedBox(width: 4),
                        Text(
                          'exit $exitCode',
                          style: TextStyle(
                            fontFamily: 'monospace',
                            fontSize: 10,
                            color: isSuccess ? Colors.green : Colors.red,
                          ),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
          if (output.isNotEmpty) ...[
            const SizedBox(height: 4),
            Text(
              output,
              style: const TextStyle(
                fontFamily: 'monospace',
                fontSize: 11,
                color: Colors.white70,
              ),
              maxLines: 5,
              overflow: TextOverflow.ellipsis,
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildMediaBadge(Map<String, dynamic> artifact) {
    final mimeType = artifact['mimeType'] ?? '';
    
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 0, 16, 12),
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: Colors.purple[100],
        borderRadius: BorderRadius.circular(4),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.image, size: 16, color: Colors.purple),
          const SizedBox(width: 4),
          Text(
            mimeType.contains('image') ? 'Screenshot' : 'Media',
            style: const TextStyle(fontSize: 12, color: Colors.purple),
          ),
        ],
      ),
    );
  }

  Widget _buildCompletedBadge(ChatMessage message) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final prUrl = message.pullRequestUrl ?? _createdPrUrl;
    final julesUrl = message.julesUrl;
    final hasPR = prUrl != null && prUrl.isNotEmpty;
    final hasPatch = message.hasPatch == true;
    final sessionId = message.sessionId;
    final prTitle = message.title ?? 'Task Completed';
    final prDescription = message.description;
    
    print('DEBUG _buildCompletedBadge: hasPR=$hasPR, hasPatch=$hasPatch, sessionId=$sessionId, julesUrl=$julesUrl');
    
    return Column(
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              decoration: BoxDecoration(
                color: Colors.green.withOpacity(0.1),
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: Colors.green.withOpacity(0.3)),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.check_circle, color: Colors.green[600], size: 16),
                  const SizedBox(width: 8),
                  Text(
                    'Work Completed',
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 14,
                      color: Colors.green[700],
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: isDark ? const Color(0xFF1E1E2E) : Colors.white,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: isDark ? Colors.grey[800]! : Colors.grey[300]!,
            ),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(0.05),
                blurRadius: 10,
                offset: const Offset(0, 4),
              ),
            ],
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: Colors.purple.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Icon(
                      Icons.description_outlined,
                      color: Colors.purple[400],
                      size: 20,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          prTitle,
                          style: TextStyle(
                            fontWeight: FontWeight.bold,
                            fontSize: 16,
                            color: isDark ? Colors.white : Colors.black87,
                          ),
                        ),
                        if (message.repoName != null)
                          Text(
                            message.repoName!,
                            style: TextStyle(
                              fontSize: 12,
                              color: isDark ? Colors.grey[500] : Colors.grey[600],
                            ),
                          ),
                      ],
                    ),
                  ),
                ],
              ),
              if (prDescription != null && prDescription.isNotEmpty) ...[
                const SizedBox(height: 12),
                Text(
                  prDescription,
                  style: TextStyle(
                    fontSize: 13,
                    height: 1.4,
                    color: isDark ? Colors.grey[300] : Colors.grey[700],
                  ),
                  maxLines: 3,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
              const SizedBox(height: 20),
              
              // Status message (success/error)
              if (_publishStatus != null) ...[
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  decoration: BoxDecoration(
                    color: _publishStatus == 'success' 
                        ? Colors.green.withOpacity(0.1) 
                        : Colors.red.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Row(
                    children: [
                      Icon(
                        _publishStatus == 'success' ? Icons.check_circle : Icons.error,
                        size: 16,
                        color: _publishStatus == 'success' ? Colors.green : Colors.red,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          _publishMessage ?? '',
                          style: TextStyle(
                            fontSize: 13,
                            color: _publishStatus == 'success' ? Colors.green[700] : Colors.red[700],
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 12),
              ],
              
              // Show appropriate button
              if (hasPR) ...[
                // PR exists - show view button
                ElevatedButton.icon(
                  onPressed: () => launchUrl(Uri.parse(prUrl!), mode: LaunchMode.externalApplication),
                  icon: const Icon(Icons.open_in_new, size: 18),
                  label: const Text('View Pull Request on GitHub'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.green[600],
                    foregroundColor: Colors.white,
                    minimumSize: const Size(double.infinity, 45),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                ),
              ] else if (_createdBranchUrl != null) ...[
                // Branch was created - show view button
                ElevatedButton.icon(
                  onPressed: () => launchUrl(Uri.parse(_createdBranchUrl!), mode: LaunchMode.externalApplication),
                  icon: const Icon(Icons.open_in_new, size: 18),
                  label: const Text('View Branch on GitHub'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.blue[600],
                    foregroundColor: Colors.white,
                    minimumSize: const Size(double.infinity, 45),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                ),
              ] else if (hasPatch && sessionId != null) ...[
                // No PR yet but we have patch data - show branch dropdown and action buttons
                
                // Branch Dropdown
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12),
                  decoration: BoxDecoration(
                    border: Border.all(color: isDark ? Colors.grey[700]! : Colors.grey[400]!),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Row(
                    children: [
                      Text('Target Branch: ', style: TextStyle(color: isDark ? Colors.white70 : Colors.black54)),
                      const SizedBox(width: 8),
                      Expanded(
                        child: _isLoadingBranches
                          ? const SizedBox(
                              height: 20,
                              child: Center(child: CircularProgressIndicator(strokeWidth: 2)),
                            )
                          : DropdownButtonHideUnderline(
                              child: DropdownButton<String>(
                                value: _availableBranches.contains(_selectedBranch) ? _selectedBranch : null,
                                hint: Text(_selectedBranch),
                                isExpanded: true,
                                dropdownColor: isDark ? const Color(0xFF2A2A3E) : Colors.white,
                                items: _availableBranches.map((branch) {
                                  return DropdownMenuItem<String>(
                                    value: branch,
                                    child: Text(branch),
                                  );
                                }).toList(),
                                onChanged: (value) {
                                  if (value != null) {
                                    setState(() => _selectedBranch = value);
                                  }
                                },
                                onTap: () {
                                  // Fetch branches on first tap if not loaded
                                  if (_availableBranches.isEmpty && message.repoName != null) {
                                    final parts = message.repoName!.split('/');
                                    if (parts.length >= 1) {
                                      // Get owner from source
                                      _fetchBranches('ivanquiroscenteno1234', parts.last);
                                    }
                                  }
                                },
                              ),
                            ),
                      ),
                      IconButton(
                        icon: Icon(_isLoadingBranches ? Icons.hourglass_empty : Icons.refresh, size: 18),
                        onPressed: _isLoadingBranches ? null : () {
                          if (message.repoName != null) {
                            _fetchBranches('ivanquiroscenteno1234', message.repoName!);
                          }
                        },
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 12),
                
                // Action Buttons Row
                Row(
                  children: [
                    // Create Branch Only button
                    Expanded(
                      child: ElevatedButton.icon(
                        onPressed: _isPublishing ? null : () => _createGitHubPR(sessionId, branchOnly: true),
                        icon: _isPublishing 
                            ? const SizedBox(
                                width: 16, 
                                height: 16, 
                                child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white)
                              )
                            : const Icon(Icons.account_tree, size: 16),
                        label: Text(_isPublishing ? '...' : 'Branch'),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.blue[600],
                          foregroundColor: Colors.white,
                          minimumSize: const Size(0, 45),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    // Create PR button
                    Expanded(
                      flex: 2,
                      child: ElevatedButton.icon(
                        onPressed: _isPublishing ? null : () => _createGitHubPR(sessionId, branchOnly: false),
                        icon: _isPublishing 
                            ? const SizedBox(
                                width: 16, 
                                height: 16, 
                                child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white)
                              )
                            : const Icon(Icons.merge, size: 16),
                        label: Text(_isPublishing ? 'Creating...' : 'Create PR'),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.purple[600],
                          foregroundColor: Colors.white,
                          minimumSize: const Size(0, 45),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                // Copy Patch button
                if (sessionId != null)
                  OutlinedButton.icon(
                    onPressed: () => _copyPatch(sessionId),
                    icon: const Icon(Icons.copy, size: 16),
                    label: const Text('Copy Patch to Clipboard'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: Colors.grey[700],
                      minimumSize: const Size(double.infinity, 40),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                    ),
                  ),
              ] else if (julesUrl != null) ...[
                // Fallback - open Jules Web
                ElevatedButton.icon(
                  onPressed: () => launchUrl(Uri.parse(julesUrl), mode: LaunchMode.externalApplication),
                  icon: const Icon(Icons.open_in_browser, size: 18),
                  label: const Text('Open in Jules Web'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.purple[600],
                    foregroundColor: Colors.white,
                    minimumSize: const Size(double.infinity, 45),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                ),
              ] else ...[
                // No patch data available
                Text(
                  'Waiting for session data...',
                  style: TextStyle(
                    fontSize: 12,
                    fontStyle: FontStyle.italic,
                    color: isDark ? Colors.grey[500] : Colors.grey[600],
                  ),
                ),
              ],
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildStatusBadge(ChatMessage msg) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Container(
      margin: const EdgeInsets.symmetric(vertical: 4),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF3A3A4E) : Colors.grey[200],
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const SizedBox(
            width: 12,
            height: 12,
            child: CircularProgressIndicator(strokeWidth: 2),
          ),
          const SizedBox(width: 8),
          Text(msg.content, style: TextStyle(color: isDark ? Colors.white70 : Colors.grey[700])),
        ],
      ),
    );
  }

  Widget _buildUserBubble(ChatMessage msg) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Align(
      alignment: Alignment.centerRight,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: isDark ? Colors.deepPurple[700] : Colors.deepPurple[100],
          borderRadius: BorderRadius.circular(12),
        ),
        child: Text(msg.content, style: TextStyle(fontSize: 16, color: isDark ? Colors.white : Colors.black87)),
      ),
    );
  }

  Widget _buildSystemBubble(ChatMessage msg) {
    return Align(
      alignment: Alignment.center,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: Colors.orange[100],
          borderRadius: BorderRadius.circular(16),
        ),
        child: Text(
          msg.content,
          style: const TextStyle(fontStyle: FontStyle.italic),
        ),
      ),
    );
  }

  Widget _buildJulesBubble(ChatMessage msg) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.all(12),
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.8,
        ),
        decoration: BoxDecoration(
          color: isDark ? const Color(0xFF2A2A3E) : Colors.grey[200],
          borderRadius: BorderRadius.circular(12),
        ),
        child: Text(msg.content, style: TextStyle(fontSize: 16, color: isDark ? Colors.white : Colors.black87)),
      ),
    );
  }

  Widget _buildWorkingIndicator() {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          color: isDark ? const Color(0xFF2A2A3E) : Colors.grey[200],
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.code, size: 20, color: Colors.deepPurple),
            const SizedBox(width: 8),
            Text(
              'Working',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.w500, color: isDark ? Colors.white : Colors.black87),
            ),
            const SizedBox(width: 8),
            _buildAnimatedDots(),
          ],
        ),
      ),
    );
  }

  Widget _buildAnimatedDots() {
    return const SizedBox(
      width: 24,
      child: Text('•••', style: TextStyle(fontSize: 16, letterSpacing: 2)),
    );
  }
}
