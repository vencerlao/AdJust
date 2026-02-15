import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:adjust_app/widgets/custom_scrollbar.dart';
import '../widgets/navigation_bar.dart';

class DetectionPage extends StatelessWidget {
  const DetectionPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Column(
        children: [
          const ResponsiveNavigationBar(currentPage: 'detection'),

          Expanded(
            child: Container(
              padding: const EdgeInsets.all(24),
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
              child: Row(
                children: [
                  /// TEXT INPUT
                  Expanded(
                    flex: 10,
                    child: Column(
                      children: [
                        Expanded(
                          child: Container(
                            padding: const EdgeInsets.all(16),
                            decoration: BoxDecoration(
                              color: Colors.white,
                              borderRadius: BorderRadius.circular(15),
                              border: Border.all(
                                color: const Color(0xFFA984AE),
                                width: 1,
                              ),
                              boxShadow: [
                                BoxShadow(
                                  color: const Color(0xFFD4B5E8).withOpacity(0.3),
                                  blurRadius: 0,
                                  offset: const Offset(0, 4),
                                ),
                              ],
                            ),
                            child: LayoutBuilder(
                              builder: (context, constraints) {
                                return CustomScrollbar(
                                  child: TextField(
                                    maxLines: null,
                                    keyboardType: TextInputType.multiline,
                                    decoration: InputDecoration(
                                      hintText: 'Paste your text here',
                                      border: InputBorder.none,
                                      contentPadding: const EdgeInsets.only(right: 20),
                                    ),
                                  ),
                                );
                              },
                            ),
                          ),
                        ),
                        const SizedBox(height: 16),
                        Align(
                          alignment: Alignment.center,
                          child: ElevatedButton(
                            onPressed: () {},
                            style: ButtonStyle(
                              padding: MaterialStateProperty.all(
                                const EdgeInsets.symmetric(horizontal: 100, vertical: 18),
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
                              'DETECT',
                              style: GoogleFonts.poppins(
                                fontSize: 18,
                                fontWeight: FontWeight.w800,
                                
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),

                  const SizedBox(width: 20),

                  /// RESULTS AREA 
                  Expanded(
                    flex: 5,
                    child: Column(
                      children: [
                        /// TOP BLANK AREA 
                        Container(
                          height: 120,
                          decoration: BoxDecoration(
                            color: const Color(0xFFF9F5FB), // Lighter area
                            borderRadius: BorderRadius.circular(15),
                            border: Border.all(
                              color: const Color(0xFFA984AE),
                              width: 1,
                            ),
                            boxShadow: [
                              BoxShadow(
                                color: const Color(0xFFD4B5E8).withOpacity(0.3),
                                blurRadius: 0,
                                offset: const Offset(0, 4),
                              ),
                            ],
                          ),
                        ),

                        const SizedBox(height: 16),

                        /// PERCENTAGES 
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 12,
                            vertical: 14,
                          ),
                          decoration: BoxDecoration(
                            color: const Color(0xFFFEE7FF), 
                            borderRadius: BorderRadius.circular(15),
                            border: Border.all(
                              color: const Color(0xFFA984AE),
                              width: 1,
                            ),
                            boxShadow: [
                              BoxShadow(
                                color: const Color(0xFFD4B5E8).withOpacity(0.3),
                                blurRadius: 0,
                                offset: const Offset(0, 4),
                              ),
                            ],
                          ),
                          child: Row(
                            mainAxisAlignment: MainAxisAlignment.spaceAround,
                            children: const [
                              _PercentageIndicator(
                                label: 'Male Coded',
                                percentage: 0,
                                color: Color(0xFFC49FC9), 
                              ),
                              _PercentageIndicator(
                                label: 'Female Coded',
                                percentage: 0,
                                color: Color(0xFFB188B6), 
                              ),
                              _PercentageIndicator(
                                label: 'Neutral',
                                percentage: 0,
                                color: Color(0xFF2D3436), 
                              ),
                            ],
                          ),
                        ),

                        const SizedBox(height: 16),

                        /// CODED WORD LISTS
                        Expanded(
                          child: Row(
                            children: const [
                              Expanded(
                                child: _CodedWordList(
                                  title: 'Masculine Coded Words',
                                  words: [],
                                ),
                              ),
                              SizedBox(width: 12),
                              Expanded(
                                child: _CodedWordList(
                                  title: 'Feminine Coded Words',
                                  words: [],
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
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

/// PERCENTAGE INDICATOR 
class _PercentageIndicator extends StatelessWidget {
  final String label;
  final int percentage;
  final Color color;

  const _PercentageIndicator({
    required this.label,
    required this.percentage,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        border: Border(
          bottom: BorderSide(
            color: color,
            width: 2.0,
          ),
        ),
      ),
      padding: const EdgeInsets.only(bottom: 2),
      child: Text(
        '$percentage% $label', 
        style: GoogleFonts.poppins(
          fontSize: 13,
          fontWeight: FontWeight.w600,
          color: color,
        ),
      ),
    );
  }
}

/// CODED WORD LIST 
class _CodedWordList extends StatelessWidget {
  final String title;
  final List<String> words;

  const _CodedWordList({
    required this.title,
    required this.words,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(15),
        border: Border.all(
          color: const Color(0xFFA984AE),
          width: 1,
        ),
        boxShadow: [
          BoxShadow(
            color: const Color(0xFFD4B5E8).withOpacity(0.3),
            blurRadius: 0,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: GoogleFonts.poppins(
              fontWeight: FontWeight.w600, 
              fontSize: 12,
              color: const Color(0xFFA984AE),
            ),
          ),
          const SizedBox(height: 12),
          Expanded(
            child: CustomScrollbar(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: words
                    .map(
                      (word) => Padding(
                        padding: const EdgeInsets.symmetric(vertical: 4),
                        child: Text(
                          word,
                          style: GoogleFonts.poppins(),
                        ),
                      ),
                    )
                    .toList(),
              ),
            ),
          ),
        ],
      ),
    );
  }
}