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

class _FeaturesTimeline extends StatelessWidget {
  const _FeaturesTimeline();

  @override
  Widget build(BuildContext context) {
    final features = [
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

    return Column(
      children: List.generate(features.length, (i) {
        final isLast = i == features.length - 1;
        return _TimelineItem(feature: features[i], isLast: isLast);
      }),
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

class _TimelineItem extends StatelessWidget {
  final _FeatureData feature;
  final bool isLast;

  const _TimelineItem({required this.feature, required this.isLast});

  @override
  Widget build(BuildContext context) {
    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 28,
            child: Column(
              children: [
                Container(
                  width: 18,
                  height: 18,
                  margin: const EdgeInsets.only(top: 6),
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: feature.isDark
                        ? const Color(0xFF3D1A6B)
                        : const Color(0xFFB08CC8),
                  ),
                ),
                if (!isLast)
                  Expanded(
                    child: Container(width: 2, color: const Color(0xFFB08CC8)),
                  ),
              ],
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Padding(
              padding: EdgeInsets.only(bottom: isLast ? 0 : 32.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    feature.title,
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
                    feature.subtitle,
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
                      const Text('• ', style: TextStyle(fontSize: 14, color: Color(0xFF444444))),
                      Expanded(
                        child: Text(
                          feature.bullet,
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
          ),
        ],
      ),
    );
  }
}

class _TeamSection extends StatelessWidget {
  const _TeamSection();

  static const _members = [
    _MemberData(
      name: 'LAO, Vencer A.',
      role: 'Performance Evaluator',
      description:
          'Tests and analyzes the model\'s accuracy, efficiency, and reliability, ensuring it meets performance standards.',
    ),
    _MemberData(
      name: 'BARBACENA, Jenny B.',
      role: 'Data Specialist',
      description:
          'Collects, cleans, and organizes datasets to ensure high-quality input for model training and evaluation',
    ),
    _MemberData(
      name: 'MIRANDA, Maria Lourdes S.',
      role: 'Model Developer',
      description:
          'Designs, implements, and trains machine learning models to detect gaze and engagement accurately.',
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
  const _MemberData({
    required this.name,
    required this.role,
    required this.description,
  });
}

class _TeamCard extends StatelessWidget {
  final _MemberData member;
  const _TeamCard({required this.member});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 220,
      child: Stack(
        clipBehavior: Clip.none,
        alignment: Alignment.topCenter,
        children: [
          Container(
            margin: const EdgeInsets.only(top: 55),
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
            padding: const EdgeInsets.fromLTRB(16, 60, 16, 20),
            child: Column(
              children: [
                Text(
                  member.name,
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.bold,
                    decoration: TextDecoration.underline,
                    color: Color(0xFF2A1040),
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  member.role,
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    fontSize: 13,
                    fontStyle: FontStyle.italic,
                    fontWeight: FontWeight.w600,
                    color: Color(0xFF3D1A6B),
                  ),
                ),
                const SizedBox(height: 12),
                Text(
                  member.description,
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    fontSize: 12,
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
              width: 110,
              height: 110,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                border: Border.all(color: const Color(0xFF7B3FA0), width: 3),
                color: const Color(0xFFE8D4F1),
              ),
              child: const Icon(Icons.person, size: 64, color: Color(0xFF7B3FA0)),
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
            '© 2025 AdJust. All rights reserved.',
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