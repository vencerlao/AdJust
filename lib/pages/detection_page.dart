import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:adjust_app/widgets/custom_scrollbar.dart';
import 'package:adjust_app/services/bias_detection_service.dart';
import 'package:fl_chart/fl_chart.dart';

class DetectionPage extends StatefulWidget {
  const DetectionPage({super.key});

  @override
  State<DetectionPage> createState() => _DetectionPageState();
}

class _DetectionPageState extends State<DetectionPage> {
  late TextEditingController _textController;
  BiasDetectionResult? _result;
  bool _isLoading = false;
  String? _error;
  int _hoveredSectionIndex = -1;

  @override
  void initState() {
    super.initState();
    _textController = TextEditingController();
  }

  @override
  void dispose() {
    _textController.dispose();
    super.dispose();
  }

  Future<void> _detectBias() async {
    final text = _textController.text.trim();
    if (text.isEmpty) {
      setState(() => _error = 'Please enter some text');
      return;
    }

    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final result = await BiasDetectionService.detectBias(text);
      setState(() {
        _result = result;
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _isLoading = false;
      });
    }
  }

  Color _getClassColor(String className) {
    switch (className) {
      case 'male_biased':
        return const Color(0xFFC49FC9);
      case 'female_biased':
        return const Color(0xFFB188B6);
      case 'neutral':
        return const Color(0xFF2D3436);
      default:
        return Colors.grey;
    }
  }

  List<String> _getWords(String key) {
    if (_result == null) return [];
    final raw = _result!.flaggedPhrases[key];
    if (raw == null) return [];
    if (raw is List<String>) return raw;
    if (raw is List) return raw.map((e) => e.toString()).toList();
    return [];
  }

  @override
  Widget build(BuildContext context) {
    return Container(
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
                            controller: _textController,
                            maxLines: null,
                            keyboardType: TextInputType.multiline,
                            onTap: () {
                              if (_error != null) {
                                setState(() => _error = null);
                              }
                            },
                            onChanged: (value) {
                              if (_error != null) {
                                setState(() => _error = null);
                              }
                              if (value.trim().isEmpty && _result != null) {
                                setState(() => _result = null);
                              }
                            },
                            decoration: InputDecoration(
                              hintText: _error ?? 'Paste your text here',
                              hintStyle: GoogleFonts.poppins(
                                color: _error != null ? Colors.red : Colors.grey,
                                fontSize: _error != null ? 14 : 13,
                                fontWeight: _error != null ? FontWeight.w400 : FontWeight.normal,
                              ),
                              border: InputBorder.none,
                              contentPadding: EdgeInsets.only(right: 20),
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
                    onPressed: _isLoading ? null : _detectBias,
                    style: ButtonStyle(
                      padding: MaterialStateProperty.all(
                        const EdgeInsets.symmetric(
                            horizontal: 100, vertical: 18),
                      ),
                      elevation: MaterialStateProperty.all(4),
                      backgroundColor:
                          MaterialStateProperty.resolveWith<Color>((states) {
                        if (states.contains(MaterialState.disabled)) {
                          return const Color(0xFFD4B5E8).withOpacity(0.6);
                        }
                        return states.contains(MaterialState.hovered)
                            ? const Color(0xFF3A0E52)
                            : const Color(0xFFD4B5E8);
                      }),
                      foregroundColor:
                          MaterialStateProperty.resolveWith<Color>((states) =>
                              states.contains(MaterialState.hovered)
                                  ? const Color(0xFFD4B5E8)
                                  : const Color(0xFF280647)),
                      shape:
                          MaterialStateProperty.resolveWith<OutlinedBorder>(
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
                    child: _isLoading
                        ? const SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : Text(
                            'DETECT',
                            style: GoogleFonts.poppins(
                              fontSize: 18,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                  ),
                ),
                // if (_error != null)
                //   Padding(
                //     padding: const EdgeInsets.only(top: 12),
                //     child: Text(
                //       _error!,
                //       style: GoogleFonts.poppins(
                //         color: Colors.red,
                //         fontSize: 12,
                //       ),
                //       textAlign: TextAlign.center,
                //     ),
                //   ),
              ],
            ),
          ),

          const SizedBox(width: 10),

          Expanded(
            flex: 5,
            child: Column(
              children: [
                Container(
                  height: 190,
                  padding: const EdgeInsets.symmetric(
                      horizontal: 20, vertical: 18),
                  decoration: BoxDecoration(
                    color: const Color(0xFFF9F5FB),
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
                  child: _result == null
                      ? Center(
                          child: Text(
                            'Detection results will appear here',
                            style: GoogleFonts.poppins(
                              color: Colors.grey,
                              fontSize: 13,
                            ),
                            textAlign: TextAlign.center,
                          ),
                        )
                      : Row(
                          crossAxisAlignment: CrossAxisAlignment.center,
                          children: [
                            SizedBox(
                              width: 170,
                              child: Stack(
                                alignment: Alignment.center,
                                children: [
                                  SizedBox(
                                    width: 110,
                                    height: 110,
                                    child: PieChart(
                                      PieChartData(
                                        centerSpaceRadius: 55,
                                        sections: [
                                          PieChartSectionData(
                                            value: (_result!.confidenceScores['male_biased'] ?? 0) * 100,
                                            color: const Color(0xFFC49FC9),
                                            title: '',
                                            radius: _hoveredSectionIndex == 0 ? 28 : 20,
                                          ),
                                          PieChartSectionData(
                                            value: (_result!.confidenceScores['female_biased'] ?? 0) * 100,
                                            color: const Color(0xFFB188B6),
                                            title: '',
                                            radius: _hoveredSectionIndex == 1 ? 28 : 20,
                                          ),
                                          PieChartSectionData(
                                            value: (_result!.confidenceScores['neutral'] ?? 0) * 100,
                                            color: const Color(0xFF2D3436),
                                            title: '',
                                            radius: _hoveredSectionIndex == 2 ? 28 : 20,
                                          ),
                                        ],
                                        borderData: FlBorderData(show: false),
                                        pieTouchData: PieTouchData(enabled: false),
                                      ),
                                    ),
                                  ),
                                  Text(
                                    _result!.detectedClass
                                        .replaceAll('_biased', '')
                                        .toUpperCase(),
                                    style: GoogleFonts.poppins(
                                      fontSize: 18,
                                      fontWeight: FontWeight.w700,
                                      color: const Color(0xFF2D3436),
                                    ),
                                  ),
                                ],
                              ),
                            ),

                            const SizedBox(width: 24),

                            Flexible(
                              child: Column(
                                mainAxisAlignment: MainAxisAlignment.center,
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    'This text is mostly classified as',
                                    style: GoogleFonts.poppins(
                                      fontSize: 14,
                                      color: Colors.grey,
                                      fontWeight: FontWeight.w500,
                                    ),
                                  ),
                                  const SizedBox(height: 4),
                                  Text(
                                    '${_result!.detectedClass.replaceAll('_', ' ').toUpperCase()} CODED',
                                    style: GoogleFonts.poppins(
                                      fontSize: 18,
                                      fontWeight: FontWeight.w800,
                                      color: _getClassColor(
                                          _result!.detectedClass),
                                    ),
                                  ),
                                  const SizedBox(height: 10),
                                  Container(
                                    height: 1,
                                    color: _getClassColor(
                                            _result!.detectedClass)
                                        .withOpacity(0.3),
                                  ),
                                  const SizedBox(height: 10),
                                  RichText(
                                    text: TextSpan(
                                      style: GoogleFonts.poppins(
                                        fontSize: 14,
                                        color: const Color(0xFF666666),
                                        height: 1.5,
                                      ),
                                      children: [
                                        const TextSpan(
                                          text: 'the indicated job advertisement is\n',
                                        ),
                                        TextSpan(
                                          text: '${_result!.detectedClass.replaceAll('_', ' ')}.',
                                          style: const TextStyle(
                                            fontWeight: FontWeight.w700,
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

                const SizedBox(height: 16),

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
                    children: [
                      _PercentageIndicator(
                        label: 'Male Biased',
                        percentage: _result != null
                            ? (_result!.confidenceScores['male_biased'] ?? 0) * 100
                            : 0,
                        color: const Color(0xFFC49FC9),
                        isHighlighted: _hoveredSectionIndex == 0,
                        onHover: (hovering) {
                          setState(() {
                            _hoveredSectionIndex = hovering ? 0 : -1;
                          });
                        },
                      ),
                      _PercentageIndicator(
                        label: 'Female Biased',
                        percentage: _result != null
                            ? (_result!.confidenceScores['female_biased'] ?? 0) * 100
                            : 0,
                        color: const Color(0xFFB188B6),
                        isHighlighted: _hoveredSectionIndex == 1,
                        onHover: (hovering) {
                          setState(() {
                            _hoveredSectionIndex = hovering ? 1 : -1;
                          });
                        },
                      ),
                      _PercentageIndicator(
                        label: 'Neutral',
                        percentage: _result != null
                            ? (_result!.confidenceScores['neutral'] ?? 0) * 100
                            : 0,
                        color: const Color(0xFF2D3436),
                        isHighlighted: _hoveredSectionIndex == 2,
                        onHover: (hovering) {
                          setState(() {
                            _hoveredSectionIndex = hovering ? 2 : -1;
                          });
                        },
                      ),
                    ],
                  ),
                ),

                const SizedBox(height: 16),

                Expanded(
                  child: Row(
                    children: [
                      Expanded(
                        child: _CodedWordList(
                          title: 'Masculine Coded Words',
                          words: _getWords('masculine'),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: _CodedWordList(
                          title: 'Feminine Coded Words',
                          words: _getWords('feminine'),
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
    );
  }
}

class _PercentageIndicator extends StatelessWidget {
  final String label;
  final double percentage;
  final Color color;
  final bool isHighlighted;
  final ValueChanged<bool> onHover;

  const _PercentageIndicator({
    required this.label,
    required this.percentage,
    required this.color,
    required this.onHover,
    this.isHighlighted = false,
  });

  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      onEnter: (_) => onHover(true),
      onExit: (_) => onHover(false),
      cursor: SystemMouseCursors.click,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        decoration: BoxDecoration(
          color: isHighlighted ? color : Colors.transparent,
          borderRadius: BorderRadius.circular(isHighlighted ? 6 : 0),
          border: isHighlighted
              ? Border.all(color: color, width: 1)
              : Border(bottom: BorderSide(color: color, width: 2.0)),
        ),
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
        child: Text(
          '${percentage.toStringAsFixed(1)}%  $label',
          style: GoogleFonts.poppins(
            fontSize: 12,
            fontWeight: FontWeight.w600,
            color: isHighlighted ? Colors.white : color,
          ),
        ),
      ),
    );
  }
}

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
            child: words.isEmpty
                ? Center(
                    child: Text(
                      'No words detected',
                      style: GoogleFonts.poppins(
                        fontSize: 11,
                        color: Colors.grey,
                      ),
                    ),
                  )
                : CustomScrollbar(
                    child: ListView.builder(
                      itemCount: words.length,
                      itemBuilder: (context, index) {
                        return Padding(
                          padding: const EdgeInsets.symmetric(vertical: 4),
                          child: Text(
                            words[index],
                            style: GoogleFonts.poppins(
                              fontSize: 12,
                              color: const Color(0xFF333333),
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        );
                      },
                    ),
                  ),
          ),
        ],
      ),
    );
  }
}