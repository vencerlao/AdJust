import 'package:flutter/material.dart';
import '../widgets/navigation_bar.dart';
import '../utils/transitions.dart';
import 'home_page.dart';
import 'detection_page.dart';
import 'dashboard_page.dart';
import 'about_page.dart';

class AppShell extends StatefulWidget {
  const AppShell({super.key});

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  final GlobalKey<NavigatorState> _navigatorKey = GlobalKey<NavigatorState>();
  String _currentPage = 'home';

  void _navigateTo(String page, Widget destination) {
    setState(() => _currentPage = page);
    _navigatorKey.currentState?.pushReplacement(
      PageTransitions.go(destination),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Column(
        children: [
          if (_currentPage != 'home')
            ResponsiveNavigationBar(
              currentPage: _currentPage,
              onNavigate: _navigateTo,
            ),

          Expanded(
            child: Navigator(
              key: _navigatorKey,
              onGenerateRoute: (_) => PageTransitions.go(
                HomePage(onNavigate: _navigateTo),
              ),
            ),
          ),
        ],
      ),
    );
  }
}