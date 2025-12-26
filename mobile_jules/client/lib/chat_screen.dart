import 'package:flutter/material.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'config.dart';

class ChatScreen extends StatefulWidget {
  final String repoName;
  final String sourceId;

  const ChatScreen({super.key, required this.repoName, required this.sourceId});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final TextEditingController _controller = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  late WebSocketChannel _channel;
  final List<String> _messages = [];
  bool _isConnected = false;
  bool _isWaiting = true; // Start waiting for initial connection response

  @override
  void initState() {
    super.initState();
    _connect();
  }

  void _connect() {
    // Convert 'http://...' to 'ws://...'
    final wsUrl = AppConfig.serverUrl.replaceFirst('http', 'ws');
    final uri = Uri.parse('$wsUrl/chat/${widget.sourceId}');
    
    try {
      _channel = WebSocketChannel.connect(uri);
      _isConnected = true;
      
      // Listen for incoming messages
      _channel.stream.listen(
        (message) {
          setState(() {
            _messages.add(message);
            // Stop waiting when we receive a Jules message
            if (message.startsWith("Jules: ")) {
              _isWaiting = false;
            }
          });
          _scrollToBottom();
        },
        onError: (error) {
          setState(() {
            _messages.add("System: Connection Error: $error");
            _isConnected = false;
            _isWaiting = false;
          });
        },
        onDone: () {
          setState(() {
            _messages.add("System: Disconnected.");
            _isConnected = false;
            _isWaiting = false;
          });
        },
      );
    } catch (e) {
      setState(() {
        _messages.add("System: Could not connect: $e");
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
        _messages.add("Me: $text");
        _isWaiting = true; // Start waiting for response
      });
      
      _channel.sink.add(text);
      _controller.clear();
      _scrollToBottom();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.repoName),
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
                // Show thinking indicator as last item when waiting
                if (_isWaiting && index == _messages.length) {
                  return _buildThinkingIndicator();
                }
                
                final msg = _messages[index];
                final isMe = msg.startsWith("Me: ");
                final isSystem = msg.startsWith("System: ");
                
                // Strip prefix for UI
                String content = msg;
                if (isMe) content = msg.substring(4);
                else if (isSystem) content = msg.substring(8);
                else if (msg.startsWith("Jules: ")) content = msg.substring(7);

                return Align(
                  alignment: isMe ? Alignment.centerRight : Alignment.centerLeft,
                  child: Container(
                    margin: const EdgeInsets.symmetric(vertical: 4),
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: isMe 
                          ? Colors.deepPurple[100] 
                          : isSystem 
                              ? Colors.orange[100] 
                              : Colors.grey[200],
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(
                      content, 
                      style: TextStyle(
                        fontSize: 16,
                        fontStyle: isSystem ? FontStyle.italic : FontStyle.normal,
                      ),
                    ),
                  ),
                );
              },
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

  Widget _buildThinkingIndicator() {
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: Colors.grey[200],
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            SizedBox(
              width: 16,
              height: 16,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                color: Colors.deepPurple,
              ),
            ),
            const SizedBox(width: 8),
            Text(
              'Jules is thinking...',
              style: TextStyle(
                fontSize: 16,
                fontStyle: FontStyle.italic,
                color: Colors.grey[600],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
