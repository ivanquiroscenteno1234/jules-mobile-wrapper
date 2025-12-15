import 'package:flutter/material.dart';
import 'home_screen.dart';

// GLOBAL CONFIGURATION
// You will need to change this IP to your computer's local IP address
// e.g., 'http://192.168.1.5:8000'
// 'http://10.0.2.2:8000' is the special alias for "localhost" on Android Emulator
const String SERVER_URL = 'http://10.0.2.2:8000';

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Mobile Jules',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.deepPurple),
        useMaterial3: true,
      ),
      home: const HomeScreen(),
    );
  }
}
