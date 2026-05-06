import 'package:flutter/material.dart';
import 'package:flutter/gestures.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:adjust_app/widgets/custom_scrollbar.dart';
import 'package:adjust_app/services/bias_detection_service.dart';
import 'package:adjust_app/constants/source_urls.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:http/http.dart' as http;
import 'package:url_launcher/url_launcher.dart';
import 'dart:convert';

const double _kFontSize = 16.0;
const double _kLineHeight = 1.45;
const FontWeight _kFontWeight = FontWeight.w400;
const EdgeInsets _kContentPadding = EdgeInsets.only(right: 27);

class DetectionPage extends StatefulWidget {
  const DetectionPage({super.key});

  @override
  State<DetectionPage> createState() => _DetectionPageState();
}

class _DetectionPageState extends State<DetectionPage> {
  late TextEditingController _textController;
  BiasDetectionResult? _result;
  BiasDetectionResult? _originalResult;
  bool _isLoading = false;
  bool _isRewriting = false;
  String? _error;
  int _hoveredSectionIndex = -1;



  Map<String, String> _rewrittenWords = {};

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
      setState(() {
        _error = 'Please enter some text';
        _result = null;
      });
      return;
    }

    final wordCount =
        text.split(RegExp(r'\s+')).where((w) => w.isNotEmpty).length;
    if (wordCount < 30) {
      final savedText = text;
      setState(() {
        _error = 'Please enter more text';
        _result = null;
        _textController.clear();
      });

      Future.delayed(const Duration(seconds: 2), () {
        if (mounted) {
          setState(() {
            _textController.value = TextEditingValue(text: savedText);
            _error = null;
          });
        }
      });

      return;
    }

    setState(() {
      _isLoading = true;
      _error = null;
      _rewrittenWords = {};
    });

    try {
      final result = await BiasDetectionService.detectBias(text);
      setState(() {
        _result = result;
        _originalResult = result;
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _isLoading = false;
      });
    }
  }

  Future<void> _rewriteToNeutral() async {
    final text = _textController.text.trim();
    if (text.isEmpty) {
      setState(() {
        _error = 'Please enter some text';
        _result = null;
      });
      return;
    }

    setState(() {
      _isRewriting = true;
      _error = null;
      _rewrittenWords = {};
    });

    try {
      final rewriteResponse =
          await BiasDetectionService.rewriteJobAdToNeutral(text);
      final rewrittenText = rewriteResponse['rewritten_text'] as String;
      final detectionResult =
          rewriteResponse['detection_result'] as BiasDetectionResult;

      final masculine = _getWords('masculine');
      final feminine = _getWords('feminine');
      final genderCodedWords = <String>{
        ...masculine.map((w) => w.toLowerCase()),
        ...feminine.map((w) => w.toLowerCase()),
      };

      final wordPattern = RegExp(r'\b[\w]+(?:-[\w]+)*\b');

      final originalWordMatches =
          wordPattern.allMatches(text.toLowerCase()).map((m) => m.group(0)!).toSet();
      final rewrittenWordMatches =
          wordPattern.allMatches(rewrittenText.toLowerCase()).map((m) => m.group(0)!).toSet();

      final removedGenderCodedWords = genderCodedWords
          .where((w) => !rewrittenWordMatches.contains(w))
          .toSet();

      final newWordsInRewritten =
          rewrittenWordMatches.difference(originalWordMatches);

      final changed = <String, String>{};

      if (removedGenderCodedWords.isNotEmpty && newWordsInRewritten.isNotEmpty) {
        final replacedMasculine =
            removedGenderCodedWords.any((w) => masculine.contains(w));
        final replacedFeminine =
            removedGenderCodedWords.any((w) => feminine.contains(w));

        final genderType = replacedMasculine ? 'masculine' : 'feminine';

        for (final newWord in newWordsInRewritten) {
          changed[newWord] = genderType;
        }
      }

      setState(() {
        _textController.value = TextEditingValue(text: rewrittenText);
        _result = detectionResult;
        _isRewriting = false;
        _rewrittenWords = changed;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _isRewriting = false;
      });
    }
  }

  Color _getClassColor(String className) {
    switch (className) {
      case 'Male':
        return const Color(0xFF8E7AB5);
      case 'Female':
        return const Color(0xFFB188B6);
      case 'Neutral':
        return const Color(0xFF7A5C9E);
      default:
        return Colors.grey;
    }
  }

  List<String> _getWords(String key, {bool useOriginal = false}) {
    final result = useOriginal ? _originalResult : _result;
    if (result == null) return [];
    return result.wordStrings(key);
  }

  List<FlaggedWord> _getFlaggedWords(String key, {bool useOriginal = false}) {
    final result = useOriginal ? _originalResult : _result;
    if (result == null) return [];
    return result.flaggedPhrases[key] ?? [];
  }

  String _getBiasType(String word) {
    final masculine = _getWords('masculine');
    if (masculine.contains(word)) return 'masculine';
    return 'feminine';
  }

  String _extractContext(String term) {
    final text = _textController.text;
    final textLower = text.toLowerCase();
    final termLower = term.toLowerCase();

    final termIndex = textLower.indexOf(termLower);
    if (termIndex == -1) return text;

    int sentenceStart = 0;
    int sentenceEnd = text.length;

    for (int i = termIndex - 1; i >= 0; i--) {
      if (text[i] == '.' || text[i] == '!' || text[i] == '?') {
        sentenceStart = i + 1;
        break;
      }
    }

    for (int i = termIndex + term.length; i < text.length; i++) {
      if (text[i] == '.' || text[i] == '!' || text[i] == '?') {
        sentenceEnd = i + 1;
        break;
      }
    }

    String sentence = text.substring(sentenceStart, sentenceEnd).trim();

    if (sentence.split(' ').length < 5 && sentenceStart > 0) {
      for (int i = sentenceStart - 2; i >= 0; i--) {
        if (text[i] == '.' || text[i] == '!' || text[i] == '?') {
          sentence = text.substring(i + 1, sentenceEnd).trim();
          break;
        }
      }
    }

    return sentence;
  }



  TextStyle get _sharedTextStyle => GoogleFonts.poppins(
        fontSize: _kFontSize,
        color: const Color(0xFF333333),
        height: _kLineHeight,
        fontWeight: _kFontWeight,
      );

  Widget _buildHighlightedTextDisplay() {
    final text = _textController.text;
    final textLower = text.toLowerCase();
    final masculine = _getWords('masculine', useOriginal: true);
    final feminine = _getWords('feminine', useOriginal: true);

    final plainStyle = _sharedTextStyle;

    List<InlineSpan> spans = [];
    int lastIndex = 0;

    List<MapEntry<int, String>> matches = [];

    for (final word in masculine) {
      final pattern = RegExp(
        r'\b' + RegExp.escape(word) + r'\b',
        caseSensitive: false,
      );
      for (final match in pattern.allMatches(textLower)) {
        matches.add(MapEntry(match.start, word));
      }
    }

    for (final word in feminine) {
      final pattern = RegExp(
        r'\b' + RegExp.escape(word) + r'\b',
        caseSensitive: false,
      );
      for (final match in pattern.allMatches(textLower)) {
        matches.add(MapEntry(match.start, word));
      }
    }

    final coveredStarts = matches.map((e) => e.key).toSet();
    for (final word in _rewrittenWords.keys) {
      if (word.isEmpty) continue;
      final pattern = RegExp(
        r'\b' + RegExp.escape(word) + r'\b',
        caseSensitive: false,
      );
      for (final match in pattern.allMatches(textLower)) {
        if (!coveredStarts.contains(match.start)) {
          matches.add(MapEntry(match.start, word));
          coveredStarts.add(match.start);
        }
      }
    }

    matches.sort((a, b) => a.key.compareTo(b.key));

    for (final match in matches) {
      final startPos = match.key;
      final wordAtPos = match.value;
      final endPos = startPos + wordAtPos.length;

      if (startPos < lastIndex) continue;

      if (startPos > lastIndex) {
        spans.add(TextSpan(
          text: text.substring(lastIndex, startPos),
          style: plainStyle,
        ));
      }

      final isMasculine = masculine.contains(wordAtPos);
      final isFeminine = feminine.contains(wordAtPos);

      final Color underlineColor;
      if (isMasculine) {
        underlineColor = const Color(0xFF8E7AB5);
      } else if (isFeminine) {
        underlineColor = const Color(0xFFB188B6);
      } else {
        underlineColor = const Color(0xFF7A5C9E);
      }

      spans.add(
        TextSpan(
          text: text.substring(startPos, endPos),
          style: plainStyle.copyWith(
            decoration: TextDecoration.underline,
            decorationColor: underlineColor,
            decorationThickness: 3.0,
          ),
        ),
      );

      lastIndex = endPos;
    }

    if (lastIndex < text.length) {
      spans.add(TextSpan(
        text: text.substring(lastIndex),
        style: plainStyle,
      ));
    }

    return SingleChildScrollView(
      child: Padding(
        padding: _kContentPadding,
        child: Text.rich(
          TextSpan(style: plainStyle, children: spans),
          textAlign: TextAlign.left,
          textDirection: TextDirection.ltr,
          strutStyle: StrutStyle(
            fontFamily: plainStyle.fontFamily,
            fontSize: _kFontSize,
            height: _kLineHeight,
            forceStrutHeight: true,
          ),
          textWidthBasis: TextWidthBasis.parent,
        ),
      ),
    );
  }

  Widget _buildTextField() {
    return SingleChildScrollView(
      child: TextField(
        controller: _textController,
        maxLines: null,
        keyboardType: TextInputType.multiline,
        style: _sharedTextStyle,
        onTap: () {
          if (_error != null) setState(() => _error = null);
        },
        onChanged: (value) {
          if (_error != null) setState(() => _error = null);
          if (value.trim().isEmpty && _result != null) {
            setState(() => _result = null);
          }
        },
        decoration: InputDecoration(
          hintText: _error ?? 'Paste your text here',
          hintStyle: GoogleFonts.poppins(
            color: _error != null ? Colors.red : Colors.grey,
            fontSize: _kFontSize,
            fontWeight: _error != null ? FontWeight.w600 : FontWeight.normal,
          ),
          border: InputBorder.none,
          contentPadding: _kContentPadding,
          isDense: false,
        ),
      ),
    );
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
                    child: CustomScrollbar(
                      child: _result != null
                          ? _buildHighlightedTextDisplay()
                          : _buildTextField(),
                    ),
                  ),
                ),

                const SizedBox(height: 16),

                Align(
                  alignment: Alignment.center,
                  child: _result != null
                      ? Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            _buildEditButton(),
                            const SizedBox(width: 12),
                            _buildRewriteButton(),
                          ],
                        )
                      : _buildDetectButton(),
                ),
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
                                            value: (_result!.confidenceScores[
                                                            'Male'] ??
                                                        0) *
                                                    100,
                                            color: const Color(0xFF8E7AB5),
                                            title: '',
                                            radius: _hoveredSectionIndex == 0
                                                ? 28
                                                : 20,
                                          ),
                                          PieChartSectionData(
                                            value: (_result!.confidenceScores[
                                                            'Female'] ??
                                                        0) *
                                                    100,
                                            color: const Color(0xFFB188B6),
                                            title: '',
                                            radius: _hoveredSectionIndex == 1
                                                ? 28
                                                : 20,
                                          ),
                                          PieChartSectionData(
                                            value: (_result!.confidenceScores[
                                                            'Neutral'] ??
                                                        0) *
                                                    100,
                                            color: const Color(0xFF7A5C9E),
                                            title: '',
                                            radius: _hoveredSectionIndex == 2
                                                ? 28
                                                : 20,
                                          ),
                                        ],
                                        borderData: FlBorderData(show: false),
                                        pieTouchData:
                                            PieTouchData(enabled: false),
                                      ),
                                    ),
                                  ),
                                  Text(
                                    _result!.detectedClass.toUpperCase(),
                                    style: GoogleFonts.poppins(
                                      fontSize: 18,
                                      fontWeight: FontWeight.w700,
                                      color: _getClassColor(
                                          _result!.detectedClass),
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
                                    '${_result!.detectedClass.toUpperCase()} CODED',
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
                                          text:
                                              'the indicated job advertisement is\n',
                                        ),
                                        TextSpan(
                                          text:
                                              '${_result!.detectedClass.toLowerCase()}.',
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
                            ? (_result!.confidenceScores['Male'] ?? 0) * 100
                            : 0,
                        color: const Color(0xFF8E7AB5),
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
                            ? (_result!.confidenceScores['Female'] ?? 0) * 100
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
                            ? (_result!.confidenceScores['Neutral'] ?? 0) * 100
                            : 0,
                        color: const Color(0xFF7A5C9E),
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
                          flaggedWords: _getFlaggedWords('masculine'),
                          bulletColor: const Color(0xFF8E7AB5),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: _CodedWordList(
                          title: 'Feminine Coded Words',
                          flaggedWords: _getFlaggedWords('feminine'),
                          bulletColor: const Color(0xFFB188B6),
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

  Widget _buildDetectButton() {
    return ElevatedButton(
      onPressed: _isLoading ? null : _detectBias,
      style: ButtonStyle(
        padding: MaterialStateProperty.all(
          const EdgeInsets.symmetric(horizontal: 100, vertical: 18),
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
    );
  }

  Widget _buildEditButton() {
    return ElevatedButton(
      onPressed: () {
        setState(() {
          _result = null;
          _originalResult = null;
          _rewrittenWords = {};
        });
      },
      style: ButtonStyle(
        padding: MaterialStateProperty.all(
          const EdgeInsets.symmetric(horizontal: 100, vertical: 18),
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
        'EDIT',
        style: GoogleFonts.poppins(
          fontSize: 18,
          fontWeight: FontWeight.w800,
        ),
      ),
    );
  }

  Widget _buildRewriteButton() {
    final bool isNeutral = _result?.detectedClass == 'Neutral';
    final bool isDisabled = _isRewriting || isNeutral;

    return Tooltip(
      message: isNeutral ? 'Text is already gender neutral' : '',
      child: ElevatedButton(
        onPressed: isDisabled ? null : _rewriteToNeutral,
        style: ButtonStyle(
          padding: MaterialStateProperty.all(
            const EdgeInsets.symmetric(horizontal: 80, vertical: 18),
          ),
          elevation: MaterialStateProperty.all(4),
          backgroundColor:
              MaterialStateProperty.resolveWith<Color>((states) {
            if (states.contains(MaterialState.disabled)) {
              return const Color(0xFFB188B6).withOpacity(0.4);
            }
            return states.contains(MaterialState.hovered)
                ? const Color(0xFF3A0E52)
                : const Color(0xFFB188B6);
          }),
          foregroundColor: MaterialStateProperty.resolveWith<Color>((states) {
            if (states.contains(MaterialState.disabled)) {
              return const Color(0xFF280647).withOpacity(0.4);
            }
            return states.contains(MaterialState.hovered)
                ? const Color(0xFFD4B5E8)
                : const Color(0xFF280647);
          }),
          shape: MaterialStateProperty.resolveWith<OutlinedBorder>((states) {
            final Color borderColor = states.contains(MaterialState.disabled)
                ? const Color(0xFF280647).withOpacity(0.2)
                : (states.contains(MaterialState.hovered)
                    ? const Color(0xFFD4B5E8)
                    : const Color(0xFF280647));

            return RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(30),
              side: BorderSide(
                color: borderColor,
                width: 2.5,
              ),
            );
          }),
        ),
        child: _isRewriting
            ? const SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(strokeWidth: 2),
              )
            : Text(
                'REWRITE',
                style: GoogleFonts.poppins(
                  fontSize: 18,
                  fontWeight: FontWeight.w800,
                ),
              ),
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
  final List<FlaggedWord> flaggedWords;
  final Color bulletColor;

  const _CodedWordList({
    required this.title,
    required this.flaggedWords,
    required this.bulletColor,
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
            child: flaggedWords.isEmpty
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
                      shrinkWrap: true,
                      physics: const NeverScrollableScrollPhysics(),
                      itemCount: flaggedWords.length,
                      itemBuilder: (context, index) {
                        final fw = flaggedWords[index];
                        final sources = splitSources(fw.source);
                        final hasLinks = sources.any((s) => s.url != null);

                        return Padding(
                          padding: const EdgeInsets.fromLTRB(0, 4, 20, 4),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.center,
                            children: [
                              Container(
                                width: 6,
                                height: 6,
                                margin: const EdgeInsets.only(right: 8),
                                decoration: BoxDecoration(
                                  color: bulletColor,
                                  shape: BoxShape.circle,
                                ),
                              ),

                              Expanded(
                                child: Text(
                                  fw.word,
                                  style: GoogleFonts.poppins(
                                    fontSize: 14,
                                    color: const Color(0xFF333333),
                                    fontWeight: FontWeight.w500,
                                  ),
                                ),
                              ),

                              if (fw.source.isNotEmpty)
                                _SourceChip(
                                  sources: sources,
                                  chipColor: bulletColor,
                                ),
                            ],
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


class _SourceChip extends StatefulWidget {
  final List<({String label, String? url})> sources;
  final Color chipColor;

  const _SourceChip({
    required this.sources,
    required this.chipColor,
  });

  @override
  State<_SourceChip> createState() => _SourceChipState();
}

class _SourceChipState extends State<_SourceChip> {
  final _layerLink = LayerLink();
  OverlayEntry? _overlayEntry;
  bool _isOverlayVisible = false;

  void _showOverlay(BuildContext context) {
    if (_isOverlayVisible) {
      _removeOverlay();
      return;
    }

    final overlay = Overlay.of(context);
    _overlayEntry = OverlayEntry(
      builder: (context) => GestureDetector(
        behavior: HitTestBehavior.translucent,
        onTap: _removeOverlay,
        child: Stack(
          children: [
            Positioned.fill(child: Container(color: Colors.transparent)),
            CompositedTransformFollower(
              link: _layerLink,
              showWhenUnlinked: false,
              offset: const Offset(0, -8),
              targetAnchor: Alignment.topRight,
              followerAnchor: Alignment.bottomRight,
              child: Material(
                color: Colors.transparent,
                child: _SourceTooltipCard(
                  sources: widget.sources,
                  chipColor: widget.chipColor,
                  onClose: _removeOverlay,
                ),
              ),
            ),
          ],
        ),
      ),
    );

    overlay.insert(_overlayEntry!);
    setState(() => _isOverlayVisible = true);
  }

  void _removeOverlay() {
    _overlayEntry?.remove();
    _overlayEntry = null;
    if (mounted) setState(() => _isOverlayVisible = false);
  }

  @override
  void dispose() {
    _removeOverlay();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final count = widget.sources.length;
    final label = count == 1 ? '1 source' : '$count sources';

    final chipBg = widget.chipColor.withOpacity(0.12);
    final chipText = widget.chipColor;

    return CompositedTransformTarget(
      link: _layerLink,
      child: GestureDetector(
        onTap: () => _showOverlay(context),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 120),
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
          decoration: BoxDecoration(
            color: _isOverlayVisible ? widget.chipColor.withOpacity(0.2) : chipBg,
            borderRadius: BorderRadius.circular(4),
            border: Border.all(
              color: widget.chipColor.withOpacity(0.35),
              width: 0.8,
            ),
          ),
          child: Text(
            label,
            style: GoogleFonts.poppins(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              color: chipText,
            ),
          ),
        ),
      ),
    );
  }
}


class _SourceTooltipCard extends StatelessWidget {
  final List<({String label, String? url})> sources;
  final Color chipColor;
  final VoidCallback onClose;

  const _SourceTooltipCard({
    required this.sources,
    required this.chipColor,
    required this.onClose,
  });

  Future<void> _launchUrl(String url) async {
    try {
      await launchUrl(Uri.parse(url));
    } catch (e) {
      debugPrint('Could not launch URL: $e');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 270,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(
          color: const Color(0xFFD4B5E8),
          width: 1.2,
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.10),
            blurRadius: 8,
            offset: const Offset(0, 3),
          ),
        ],
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Sources',
                style: GoogleFonts.poppins(
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                  color: const Color(0xFFA984AE),
                  letterSpacing: 0.4,
                ),
              ),
              GestureDetector(
                onTap: onClose,
                child: Icon(
                  Icons.close_rounded,
                  size: 14,
                  color: Colors.grey.shade400,
                ),
              ),
            ],
          ),

          const SizedBox(height: 8),

          ...sources.map((s) {
            final hasUrl = s.url != null;
            return Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: GestureDetector(
                onTap: hasUrl ? () => _launchUrl(s.url!) : null,
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Padding(
                      padding: const EdgeInsets.only(top: 1, right: 5),
                      child: Icon(
                        hasUrl ? Icons.open_in_new_rounded : Icons.info_outline_rounded,
                        size: 11,
                        color: hasUrl
                            ? chipColor
                            : Colors.grey.shade400,
                      ),
                    ),

                    Expanded(
                      child: Text(
                        s.label,
                        style: GoogleFonts.poppins(
                          fontSize: 12,
                          fontWeight: FontWeight.w500,
                          color: hasUrl
                              ? chipColor
                              : Colors.grey.shade500,
                          decoration: hasUrl
                              ? TextDecoration.underline
                              : TextDecoration.none,
                          decorationColor: chipColor,
                          height: 1.4,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            );
          }),
        ],
      ),
    );
  }
}