import 'package:flutter/foundation.dart' show kIsWeb;

class AppConfig {
  // Use localhost for web, 10.0.2.2 for Android emulator
  static String serverUrl = kIsWeb ? 'http://localhost:8000' : 'http://10.0.2.2:8000';
  
  // Auto mode: auto-approve plans and create PRs
  static bool autoMode = false;
  
  // Dark mode theme
  static bool darkMode = false;  // Default to light mode
}
