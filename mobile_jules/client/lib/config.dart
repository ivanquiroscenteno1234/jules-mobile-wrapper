import 'package:flutter/foundation.dart' show kIsWeb;

class AppConfig {
  // Server URL - using ngrok for remote access
  static String serverUrl = 'https://jada-volatilisable-fiendishly.ngrok-free.dev';
  
  // Auto mode: auto-approve plans and create PRs
  static bool autoMode = false;
  
  // Dark mode theme
  static bool darkMode = false;  // Default to light mode
}
