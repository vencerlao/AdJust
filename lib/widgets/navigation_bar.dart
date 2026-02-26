import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../pages/home_page.dart';
import '../pages/detection_page.dart';
import '../pages/dashboard_page.dart';
import '../pages/about_page.dart';

class ResponsiveNavigationBar extends StatelessWidget {
  final String currentPage;
  final void Function(String page, Widget destination) onNavigate;

  const ResponsiveNavigationBar({
    super.key,
    required this.currentPage,
    required this.onNavigate,
  });

  @override
  Widget build(BuildContext context) {
    final bool isMobile = MediaQuery.of(context).size.width < 600;

    return Container(
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [
            Color(0xFFFFFFF0),
            Color(0xFFE9B3FB),
            Color(0xFF3A0E52),
            Color(0xFF3A0E52),
          ],
          stops: [0.0, 0.4, 0.8, 1.0],
          begin: Alignment.centerLeft,
          end: Alignment.centerRight,
        ),
        border: const Border(
          bottom: BorderSide(
            color: Color(0xFFA984AE),
            width: 3,
          ),
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.1),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Padding(
        padding: EdgeInsets.symmetric(
          horizontal: isMobile ? 16 : 32,
          vertical: isMobile ? 12 : 16,
        ),
        child: isMobile
            ? _MobileNav(currentPage: currentPage, onNavigate: onNavigate)
            : _DesktopNav(currentPage: currentPage, onNavigate: onNavigate),
      ),
    );
  }
}

class _DesktopNav extends StatelessWidget {
  final String currentPage;
  final void Function(String page, Widget destination) onNavigate;

  const _DesktopNav({
    required this.currentPage,
    required this.onNavigate,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        _Logo(onTap: () => onNavigate('home', HomePage(onNavigate: onNavigate))),
        Row(
          children: [
          _NavItem(
            label: 'HOME',
            isActive: currentPage == 'home',
            onTap: () => onNavigate('home', HomePage(onNavigate: onNavigate)),
          ),
          const SizedBox(width: 50),
          _NavItem(
            label: 'DETECT',
            isActive: currentPage == 'detection',
            onTap: () => onNavigate('detection', const DetectionPage()),
          ),
          const SizedBox(width: 50),
          _NavItem(
            label: 'DASHBOARD',
            isActive: currentPage == 'dashboard',
            onTap: () => onNavigate('dashboard', const DashboardPage()),
          ),
          const SizedBox(width: 50),
          _NavItem(
            label: 'ABOUT',
            isActive: currentPage == 'about',
            onTap: () => onNavigate('about', const AboutPage()),
          ),
        ],
      ),
      ],
    );
  }
}

class _MobileNav extends StatefulWidget {
  final String currentPage;
  final void Function(String page, Widget destination) onNavigate;

  const _MobileNav({required this.currentPage, required this.onNavigate});

  @override
  State<_MobileNav> createState() => _MobileNavState();
}

class _MobileNavState extends State<_MobileNav> {
  bool _isMenuOpen = false;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        _Logo(onTap: () => widget.onNavigate('home', HomePage(onNavigate: widget.onNavigate))),
        IconButton(
          icon: Icon(
            _isMenuOpen ? Icons.close : Icons.menu,
            color: Colors.white,
            size: 28,
          ),
          onPressed: () => setState(() => _isMenuOpen = !_isMenuOpen),
        ),
      ],
    );
  }
}

class _Logo extends StatelessWidget {
  final VoidCallback onTap;
  const _Logo({required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Image.asset(
        'assets/images/adjust_logo.png',
        height: 35,
        fit: BoxFit.contain,
      ),
    );
  }
}

class _NavItem extends StatefulWidget {
  final String label;
  final bool isActive;
  final VoidCallback onTap;

  const _NavItem({
    required this.label,
    required this.isActive,
    required this.onTap,
  });

  @override
  State<_NavItem> createState() => _NavItemState();
}

class _NavItemState extends State<_NavItem> {
  bool _isHovered = false;

  @override
  Widget build(BuildContext context) {
    final bool showLine = widget.isActive || _isHovered;
    final Color lineColor = widget.isActive ? Colors.white : Colors.white70;

    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _isHovered = true),
      onExit: (_) => setState(() => _isHovered = false),
      child: GestureDetector(
        onTap: widget.onTap,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Text(
              widget.label,
              style: GoogleFonts.poppins(
                fontSize: 16,
                fontWeight: FontWeight.w600,
                color: showLine ? Colors.white : Colors.white70,
              ),
            ),
            const SizedBox(height: 4),
            Center(
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 250),
                curve: Curves.easeInOut,
                height: 3,
                width: showLine ? _textWidth(widget.label) : 0,
                decoration: BoxDecoration(
                  color: lineColor,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  double _textWidth(String text) {
    final TextPainter painter = TextPainter(
      text: TextSpan(
        text: text,
        style: GoogleFonts.poppins(
          fontSize: 16,
          fontWeight: FontWeight.w600,
        ),
      ),
      maxLines: 1,
      textDirection: TextDirection.ltr,
    )..layout();

    return painter.width;
  }
}