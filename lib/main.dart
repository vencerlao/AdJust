import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'pages/home_page.dart';
import 'pages/about_page.dart';
import 'pages/dashboard_page.dart';
import 'pages/detection_page.dart';

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Adjust',
      theme: ThemeData(
        textTheme: GoogleFonts.poppinsTextTheme(
          ThemeData.light().textTheme,
        ).copyWith(
          bodyLarge: GoogleFonts.poppins(
            textStyle: ThemeData.light().textTheme.bodyLarge,
          ),
          bodyMedium: GoogleFonts.poppins(
            textStyle: ThemeData.light().textTheme.bodyMedium,
          ),
          bodySmall: GoogleFonts.poppins(
            textStyle: ThemeData.light().textTheme.bodySmall,
          ),
          displayLarge: GoogleFonts.poppins(
            textStyle: ThemeData.light().textTheme.displayLarge,
          ),
          displayMedium: GoogleFonts.poppins(
            textStyle: ThemeData.light().textTheme.displayMedium,
          ),
          displaySmall: GoogleFonts.poppins(
            textStyle: ThemeData.light().textTheme.displaySmall,
          ),
          headlineLarge: GoogleFonts.poppins(
            textStyle: ThemeData.light().textTheme.headlineLarge,
          ),
          headlineMedium: GoogleFonts.poppins(
            textStyle: ThemeData.light().textTheme.headlineMedium,
          ),
          headlineSmall: GoogleFonts.poppins(
            textStyle: ThemeData.light().textTheme.headlineSmall,
          ),
          labelLarge: GoogleFonts.poppins(
            textStyle: ThemeData.light().textTheme.labelLarge,
          ),
          labelMedium: GoogleFonts.poppins(
            textStyle: ThemeData.light().textTheme.labelMedium,
          ),
          labelSmall: GoogleFonts.poppins(
            textStyle: ThemeData.light().textTheme.labelSmall,
          ),
          titleLarge: GoogleFonts.poppins(
            textStyle: ThemeData.light().textTheme.titleLarge,
          ),
          titleMedium: GoogleFonts.poppins(
            textStyle: ThemeData.light().textTheme.titleMedium,
          ),
          titleSmall: GoogleFonts.poppins(
            textStyle: ThemeData.light().textTheme.titleSmall,
          ),
        ),
        primarySwatch: Colors.purple,
        fontFamily: 'Poppins',
      ),
      home: const HomePage(),
      routes: {
        '/home': (context) => const HomePage(),
        '/about': (context) => const AboutPage(),
        '/dashboard': (context) => const DashboardPage(),
        '/detection': (context) => const DetectionPage(),
      },
    );
  }
}
