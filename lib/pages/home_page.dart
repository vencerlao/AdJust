import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'detection_page.dart';
import 'dashboard_page.dart';
import 'about_page.dart';

class HomePage extends StatelessWidget {
  final void Function(String page, Widget destination) onNavigate;

  const HomePage({super.key, required this.onNavigate});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            Color(0xFFF1C8FE),
            Color(0xFFF6EDE6),
            Color(0xFFFAF5ED),
          ],
        ),
      ),
      child: Center(
        child: SingleChildScrollView(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: Image.asset(
                  'assets/images/adjust_logo.png',
                  width: 800,
                  height: 200,
                  fit: BoxFit.contain,
                ),
              ),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 30),
                child: Text(
                  '"A website for gender detection, mitigation, and awareness"', 
                  textAlign: TextAlign.center,
                  style: GoogleFonts.poppins(
                    fontSize: 24,
                    fontStyle: FontStyle.italic,
                    color: const Color(0xFF280647),
                    height: 1.5,
                  ),
                ),
              ),

              const SizedBox(height: 25),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 32),
                child: Column(
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        SizedBox(
                          width: 300,
                          child: _ActionButton(
                            label: 'DETECT',
                            onPressed: () => onNavigate('detection', const DetectionPage()),
                          ),
                        ),
                        const SizedBox(width: 24),
                        SizedBox(
                          width: 300,
                          child: _ActionButton(
                            label: 'DASHBOARD',
                            onPressed: () => onNavigate('dashboard', const DashboardPage()),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    SizedBox(
                      width: 300,
                      child: _ActionButton(
                        label: 'ABOUT',
                        onPressed: () => onNavigate('about', const AboutPage()),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ActionButton extends StatelessWidget {
  final String label;
  final VoidCallback onPressed;

  const _ActionButton({
    required this.label,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    return ElevatedButton(
      onPressed: onPressed,
      style: ButtonStyle(
        padding: MaterialStateProperty.all(
          const EdgeInsets.symmetric(vertical: 16),
        ),
        elevation: MaterialStateProperty.all(4),
        backgroundColor: MaterialStateProperty.resolveWith<Color>(
          (states) => states.contains(MaterialState.hovered)
              ? const Color(0xFF3A0E52)
              : const Color(0xFFD4B5E8),
        ),
        foregroundColor: MaterialStateProperty.resolveWith<Color>(
          (states) => states.contains(MaterialState.hovered)
              ? const Color(0xFFD4B5E8)
              : const Color(0xFF280647),
        ),
        shape: MaterialStateProperty.resolveWith<OutlinedBorder>(
          (states) => RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(30),
            side: BorderSide(
              color: states.contains(MaterialState.hovered)
                  ? const Color(0xFFD4B5E8)
                  : const Color(0xFF280647),
              width: 2.5,
            ),
          ),
        ),
      ),
      child: Text(
        label,
        style: GoogleFonts.poppins(
          fontSize: 24,
          fontWeight: FontWeight.w800,
          letterSpacing: 1.2,
        ),
      ),
    );
  }
}