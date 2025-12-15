import 'package:flutter/material.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'main.dart'; // To access SERVER_URL

class ChatScreen extends StatefulWidget {
  final String repoName;
  final String sourceId;

  const ChatScreen({super.key, required this.repoName, required this.sourceId});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final TextEditingController _controller = TextEditingController();
  late WebSocketChannel _channel;
  final List<String> _messages = [];
  bool _isConnected = false;

  @override
  void initState() {
    super.initState();
    _connect();
  }

  void _connect() {
    // Convert 'http://...' to 'ws://...'
    final wsUrl = SERVER_URL.replaceFirst('http', 'ws');
    // We must encode the sourceId because it contains slashes (e.g. "sources/github/...")
    // But our backend defines `{source_id:path}` which handles raw slashes.
    // However, just to be safe, if we send it as part of the path, we should assume the backend handles it.
    // The backend uses `{source_id:path}`, so "sources/github/a/b" is valid.
    final uri = Uri.parse('$wsUrl/chat/${widget.sourceId}');
    
    try {
      _channel = WebSocketChannel.connect(uri);
      _isConnected = true;
      
      // Listen for incoming messages
      _channel.stream.listen(
        (message) {
          setState(() {
            _messages.add(message); // Message already formatted by server as "Jules: ..." or "System: ..."
          });
        },
        onError: (error) {
          setState(() {
            _messages.add("System: Connection Error: $error");
            _isConnected = false;
          });
        },
        onDone: () {
          setState(() {
            _messages.add("System: Disconnected.");
            _isConnected = false;
          });
        },
      );
    } catch (e) {
      setState(() {
        _messages.add("System: Could not connect: $e");
        _isConnected = false;
      });
    }
  }

  @override
  void dispose() {
    if (_isConnected) {
        _channel.sink.close();
    }
    _controller.dispose();
    super.dispose();
  }

  void _sendMessage() {
    if (_controller.text.isNotEmpty && _isConnected) {
      final text = _controller.text;
      
      setState(() {
        _messages.add("Me: $text");
      });
      
      _channel.sink.add(text);
      _controller.clear();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('${widget.repoName}'),
        backgroundColor: Theme.of(context).colorScheme.inversePrimary,
      ),
      body: Column(
        children: [
          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: _messages.length,
              itemBuilder: (context, index) {
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
                  onPressed: _sendMessage,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
