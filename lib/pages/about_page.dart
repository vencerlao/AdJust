import 'package:flutter/material.dart';
import '../widgets/custom_scrollbar.dart';

class AboutPage extends StatelessWidget {
  const AboutPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      decoration: const BoxDecoration(
        gradient: RadialGradient(
          center: Alignment(-0.9, -0.9),
          radius: 3.0,
          focal: Alignment(-0.6, -0.6),
          focalRadius: 0.1,
          colors: [
            Color(0xFFE8D4F1),
            Color(0xFFF6EDE6),
            Color(0xFFFAF5ED),
          ],
          stops: [0.0, 0.45, 1.0],
        ),
      ),
      child: CustomScrollbar(
        child: SingleChildScrollView(
          child: Column(
            children: const [
              _FeaturesSection(),
              _TeamSection(),
              _FooterSection(),
            ],
          ),
        ),
      ),
    );
  }
}


class _FeaturesSection extends StatelessWidget {
  const _FeaturesSection();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 60.0, vertical: 48.0),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Expanded(
            flex: 5,
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Image.asset(
                  'assets/images/adjust_logo.png',
                  height: 230,
                  fit: BoxFit.contain,
                  alignment: Alignment.centerLeft,
                ),
                const SizedBox(height: 8),
                RichText(
                  text: const TextSpan(
                    style: TextStyle(
                      fontSize: 24,
                      fontFamily: 'Poppins',
                      color: Color(0xFF280647),
                      fontStyle: FontStyle.italic,
                    ),
                    children: [
                      TextSpan(text: '  Making job '),
                      TextSpan(
                        text: 'ads just',
                        style: TextStyle(fontWeight: FontWeight.bold),
                      ),
                      TextSpan(text: ' the way they should be'),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 40),
          Expanded(
            flex: 5,
            child: const _FeaturesTimeline(),
          ),
        ],
      ),
    );
  }
}

class _FeatureData {
  final String title;
  final String subtitle;
  final String bullet;
  final bool isDark;
  const _FeatureData({
    required this.title,
    required this.subtitle,
    required this.bullet,
    required this.isDark,
  });
}


class _FeaturesTimeline extends StatelessWidget {
  const _FeaturesTimeline();

  static const _features = [
    _FeatureData(
      title: 'Gender Bias Detection',
      subtitle: 'Identifies subtle and explicit gender-biased terms in job advertisements using NLP.',
      bullet: 'AdJust scans your text and highlights words or patterns that may influence gendered interpretations during recruitment.',
      isDark: true,
    ),
    _FeatureData(
      title: 'Mitigation',
      subtitle: 'Provides clear, gender-neutral alternatives to biased language.',
      bullet: 'Once bias is detected, AdJust offers suggested replacements to help you rewrite job ads in a fair, inclusive, and professional way.',
      isDark: false,
    ),
    _FeatureData(
      title: 'Awareness',
      subtitle: 'Visualizes the prevalence of gender bias across ten years.',
      bullet: 'The dashboard shows patterns, trends, and overall bias levels—empowering you to monitor improvements and maintain inclusive hiring practices.',
      isDark: false,
    ),
  ];

  static const double _itemHeight = 150.0;
  static const double _leftDotX = 12.0;
  static const double _rightDotX = 52.0;
  static const double _dotAreaWidth = 70.0;
  static const double _dotTopOffset = 17.0;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      height: _itemHeight * _features.length,
      child: Stack(
        children: [
          Positioned.fill(
            child: CustomPaint(
              painter: _ZigzagPainter(
                itemCount: _features.length,
                itemHeight: _itemHeight,
                leftDotX: _leftDotX,
                rightDotX: _rightDotX,
                dotTopOffset: _dotTopOffset,
              ),
            ),
          ),

          Column(
            children: List.generate(_features.length, (i) {
              final f = _features[i];
              final bool isLeft = i % 2 == 0;
              final double dotX = isLeft ? _leftDotX : _rightDotX;
              final double dotSize = f.isDark ? 22 : 16;

              return SizedBox(
                height: _itemHeight,
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    SizedBox(
                      width: _dotAreaWidth,
                      child: Stack(
                        children: [
                          Positioned(
                            top: _dotTopOffset - dotSize / 2,
                            left: dotX - dotSize / 2,
                            child: Container(
                              width: dotSize,
                              height: dotSize,
                              decoration: BoxDecoration(
                                shape: BoxShape.circle,
                                color: f.isDark
                                    ? const Color(0xFF3D1A6B)
                                    : const Color(0xFFB08CC8),
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            f.title,
                            style: const TextStyle(
                              fontSize: 22,
                              fontFamily: 'Poppins',
                              fontWeight: FontWeight.w700,
                              fontStyle: FontStyle.italic,
                              color: Color(0xFF2A1040),
                            ),
                          ),
                          const SizedBox(height: 6),
                          Text(
                            f.subtitle,
                            style: const TextStyle(
                              fontSize: 14,
                              fontFamily: 'Poppins',
                              fontWeight: FontWeight.w700,
                              color: Color(0xFF2A1040),
                            ),
                          ),
                          const SizedBox(height: 6),
                          Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Text(
                                '• ',
                                style: TextStyle(
                                  fontSize: 14,
                                  color: Color(0xFF444444),
                                ),
                              ),
                              Expanded(
                                child: Text(
                                  f.bullet,
                                  style: const TextStyle(
                                    fontSize: 14,
                                    fontFamily: 'Poppins',
                                    fontWeight: FontWeight.w500,
                                    color: Color(0xFF2A1040),
                                    height: 1.5,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              );
            }),
          ),
        ],
      ),
    );
  }
}

class _ZigzagPainter extends CustomPainter {
  final int itemCount;
  final double itemHeight;
  final double leftDotX;
  final double rightDotX;
  final double dotTopOffset;

  const _ZigzagPainter({
    required this.itemCount,
    required this.itemHeight,
    required this.leftDotX,
    required this.rightDotX,
    required this.dotTopOffset,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = const Color(0xFFB08CC8)
      ..strokeWidth = 2.0
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    for (int i = 0; i < itemCount - 1; i++) {
      final double startX = (i % 2 == 0) ? leftDotX : rightDotX;
      final double endX   = (i % 2 == 0) ? rightDotX : leftDotX;
      final double startY = i * itemHeight + dotTopOffset;
      final double endY   = (i + 1) * itemHeight + dotTopOffset;

      canvas.drawLine(
        Offset(startX, startY),
        Offset(endX, endY),
        paint,
      );
    }
  }

  @override
  bool shouldRepaint(_ZigzagPainter oldDelegate) =>
      oldDelegate.itemHeight != itemHeight ||
      oldDelegate.itemCount != itemCount;
}

class _TeamSection extends StatelessWidget {
  const _TeamSection();

  static const _members = [
    _MemberData(
      name: 'LAO, Vencer A.',
      role: 'Web Developer',
      description:
          'Spearheads the system\’s web development framework and user interface, ensuring a seamless and intuitive user experience. Responsible for establishing the foundational data dictionary of gender-coded words, defining the linguistic parameters used for detection. Facilitated the integration of the gender-neutral rewriting API, optimizing the integration pipeline to ensure real-time text transformations are both technically robust and inclusive.',
      imagePath: 'assets/images/vencer.jpg',
    ),
    _MemberData(
      name: 'BARBACENA, Jenny B.',
      role: 'Data Analyst',
      description:
          'Handles historical data collection, preprocessing, and temporal analysis of over 427,000 job advertisement entries. Responsible for conducting exploratory data analysis, performing Mann-Kendall trend analysis to identify patterns of gender bias across ten industries over a ten-year period, and developing the analytics dashboard of the web application.\n\n\n',
      imagePath: 'assets/images/jenny.jpg',
    ),
    _MemberData(
      name: 'MIRANDA, Maria Lourdes S.',
      role: 'Machine Learning &\n Data Engineer',
      description:
          'Led the end-to-end system development, including web scraping pipeline design and implementation for job advertisement data collection. Performed data preprocessing and dataset construction for model training. Developed, trained, and iteratively optimized the gender bias detection model, and implemented its integration into the system for classification and prediction.',
      imagePath: 'assets/images/lourdes.jpg',
    ),
  ];

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 60.0, vertical: 48.0),
      child: Column(
        children: [
          const Text(
            'MEET THE TEAM',
            style: TextStyle(
              fontSize: 36,
              fontWeight: FontWeight.bold,
              letterSpacing: 6,
              color: Color(0xFF3D1A6B),
            ),
          ),
          const SizedBox(height: 40),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: _members
                .map((m) => Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 16.0),
                      child: _TeamCard(member: m),
                    ))
                .toList(),
          ),
        ],
      ),
    );
  }
}

class _MemberData {
  final String name;
  final String role;
  final String description;
  final String imagePath;
  const _MemberData({
    required this.name,
    required this.role,
    required this.description,
    required this.imagePath,
  });
}

class _TeamCard extends StatelessWidget {
  final _MemberData member;
  const _TeamCard({required this.member});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 280,
      child: Stack(
        clipBehavior: Clip.none,
        alignment: Alignment.topCenter,
        children: [
          Container(
            margin: const EdgeInsets.only(top: 75),
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.85),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: const Color(0xFF7B3FA0), width: 2),
              boxShadow: [
                BoxShadow(
                  color: const Color(0xFF7B3FA0).withOpacity(0.15),
                  blurRadius: 16,
                  offset: const Offset(0, 6),
                ),
              ],
            ),
            padding: const EdgeInsets.fromLTRB(20, 80, 20, 24),
            child: Column(
              children: [
                Text(
                  member.name,
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.bold,
                    decoration: TextDecoration.underline,
                    color: Color(0xFF2A1040),
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  member.role,
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    fontSize: 14,
                    fontStyle: FontStyle.italic,
                    fontWeight: FontWeight.w600,
                    color: Color(0xFF3D1A6B),
                  ),
                ),
                const SizedBox(height: 14),
                Text(
                  member.description,
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    fontSize: 13,
                    color: Color(0xFF444444),
                    height: 1.5,
                    fontStyle: FontStyle.italic,
                  ),
                ),
              ],
            ),
          ),
          Positioned(
            top: 0,
            child: Container(
              width: 140,
              height: 140,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                border: Border.all(color: const Color(0xFF7B3FA0), width: 3),
                color: const Color(0xFFE8D4F1),
              ),
              child: ClipOval(
                child: Image.asset(
                  member.imagePath,
                  fit: BoxFit.cover,
                  alignment: Alignment.center,
                  filterQuality: FilterQuality.high,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _FooterSection extends StatelessWidget {
  const _FooterSection();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(vertical: 20, horizontal: 60),
      decoration: const BoxDecoration(
        border: Border(
          top: BorderSide(color: Color(0xFFD0B0E8), width: 1),
        ),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Text(
            '© 2026 AdJust. All rights reserved.',
            style: TextStyle(fontSize: 13, color: Color(0xFF555555)),
          ),
          const SizedBox(width: 12),
          _FooterIcon(icon: Icons.camera_alt_outlined, onTap: () {}),
          const SizedBox(width: 8),
          _FooterIcon(icon: Icons.facebook, onTap: () {}),
          const SizedBox(width: 8),
          _FooterIcon(icon: Icons.mail_outline, onTap: () {}),
        ],
      ),
    );
  }
}

class _FooterIcon extends StatelessWidget {
  final IconData icon;
  final VoidCallback onTap;
  const _FooterIcon({required this.icon, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(4),
      child: Icon(icon, size: 20, color: const Color(0xFF555555)),
    );
  }
}