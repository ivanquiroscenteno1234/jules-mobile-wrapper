import 'package:flutter/material.dart';
import 'home_screen.dart';
import 'config.dart';

void main() {
  runApp(const MyApp());
}

class MyApp extends StatefulWidget {
  const MyApp({super.key});

  // Allow toggling theme from anywhere
  static void setThemeMode(BuildContext context, ThemeMode mode) {
    final state = context.findAncestorStateOfType<_MyAppState>();
    state?.setThemeMode(mode);
  }

  @override
  State<MyApp> createState() => _MyAppState();
}

class _MyAppState extends State<MyApp> {
  ThemeMode _themeMode = ThemeMode.system;

  void setThemeMode(ThemeMode mode) {
    setState(() {
      _themeMode = mode;
      AppConfig.darkMode = mode == ThemeMode.dark;
    });
  }

  @override
  void initState() {
    super.initState();
    _themeMode = AppConfig.darkMode ? ThemeMode.dark : ThemeMode.light;
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Mobile Jules',
      themeMode: _themeMode,
      
      // Light Theme
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: Colors.deepPurple,
          brightness: Brightness.light,
        ),
        useMaterial3: true,
        appBarTheme: const AppBarTheme(
          centerTitle: true,
          elevation: 0,
        ),
        cardTheme: CardThemeData(
          elevation: 2,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        ),
      ),
      
      // Dark Theme with high contrast text
      darkTheme: ThemeData(
        brightness: Brightness.dark,
        colorScheme: ColorScheme.dark(
          primary: Colors.deepPurple[300]!,
          secondary: Colors.purpleAccent[100]!,
          surface: const Color(0xFF1E1E2E),
          background: const Color(0xFF11111B),
          onSurface: Colors.white,
          onBackground: Colors.white,
        ),
        useMaterial3: true,
        scaffoldBackgroundColor: const Color(0xFF11111B),
        
        // Text themes with bright colors
        textTheme: const TextTheme(
          bodyLarge: TextStyle(color: Colors.white),
          bodyMedium: TextStyle(color: Colors.white),
          bodySmall: TextStyle(color: Colors.white70),
          titleLarge: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
          titleMedium: TextStyle(color: Colors.white),
          labelLarge: TextStyle(color: Colors.white),
        ),
        
        appBarTheme: const AppBarTheme(
          centerTitle: true,
          elevation: 0,
          backgroundColor: Color(0xFF1E1E2E),
          foregroundColor: Colors.white,
          titleTextStyle: TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.w600),
        ),
        
        cardTheme: CardThemeData(
          elevation: 4,
          color: const Color(0xFF2A2A3E),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        ),
        
        listTileTheme: const ListTileThemeData(
          iconColor: Colors.white,
          textColor: Colors.white,
          subtitleTextStyle: TextStyle(color: Colors.white70),
        ),
        
        inputDecorationTheme: InputDecorationTheme(
          filled: true,
          fillColor: const Color(0xFF2A2A3E),
          hintStyle: const TextStyle(color: Colors.white54),
          labelStyle: const TextStyle(color: Colors.white),
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(8),
            borderSide: BorderSide.none,
          ),
        ),
        
        chipTheme: ChipThemeData(
          backgroundColor: const Color(0xFF3A3A4E),
          labelStyle: const TextStyle(color: Colors.white),
        ),
        
        iconTheme: const IconThemeData(color: Colors.white),
      ),
      
      home: const HomeScreen(),
    );
  }
}
