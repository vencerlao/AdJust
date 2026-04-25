import 'package:flutter/material.dart';
import 'package:flutter/gestures.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:adjust_app/widgets/custom_scrollbar.dart';
import 'package:adjust_app/widgets/word_suggestions.dart';
import 'package:adjust_app/services/bias_detection_service.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:http/http.dart' as http;
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
  bool _isLoading = false;
  bool _isRewriting = false;
  String? _error;
  int _hoveredSectionIndex = -1;

  Map<String, String> _suggestions = {};
  Map<String, bool> _suggestionLoading = {};
  Map<String, String?> _suggestionErrors = {};
  String? _hoveredWord;

  late final ValueNotifier<int> _suggestionUpdateNotifier = ValueNotifier(0);

  @override
  void initState() {
    super.initState();
    _textController = TextEditingController();
  }

  @override
  void dispose() {
    _textController.dispose();
    _suggestionUpdateNotifier.dispose();
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

    final wordCount = text.split(RegExp(r'\s+')).where((w) => w.isNotEmpty).length;
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
      _suggestions.clear();
      _suggestionLoading.clear();
      _suggestionErrors.clear();
      _hoveredWord = null;
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
      _suggestions.clear();
      _suggestionLoading.clear();
      _suggestionErrors.clear();
      _hoveredWord = null;
    });

    try {
      final rewriteResponse = await BiasDetectionService.rewriteJobAdToNeutral(text);
      final rewrittenText = rewriteResponse['rewritten_text'] as String;
      final detectionResult = rewriteResponse['detection_result'] as BiasDetectionResult;

      setState(() {
        _textController.value = TextEditingValue(text: rewrittenText);
        _result = detectionResult;
        _isRewriting = false;
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

  List<String> _getWords(String key) {
    if (_result == null) return [];
    final raw = _result!.flaggedPhrases[key];
    if (raw == null) return [];
    if (raw is List<String>) return raw;
    if (raw is List) return raw.map((e) => e.toString()).toList();
    return [];
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

  Future<void> _fetchSuggestion(String term) async {
    if (_suggestions.containsKey(term)) {
      _suggestionUpdateNotifier.value++;
      return;
    }

    setState(() {
      _suggestionLoading[term] = true;
      _suggestionErrors[term] = null;
    });

    try {
      final biasType = _getBiasType(term);
      final context = _extractContext(term);

      final suggestion = await BiasDetectionService.getContextAwareSuggestion(
        term,
        biasType,
        context: context,
      );

      setState(() {
        _suggestions[term] = suggestion.suggestion;
        _suggestionLoading[term] = false;
        _suggestionUpdateNotifier.value++;
      });
    } catch (e) {
      setState(() {
        _suggestionLoading[term] = false;
        _suggestionErrors[term] = 'No suggestion available';
        _suggestionUpdateNotifier.value++;
      });
    }
  }

  void _acceptSuggestion(String originalWord, String suggestion) {
    final updatedText = _textController.text.replaceAll(
      RegExp(r'\b' + RegExp.escape(originalWord) + r'\b'),
      suggestion,
    );

    setState(() {
      _textController.value = TextEditingValue(text: updatedText);
      _hoveredWord = null;
      _suggestions.clear();
      _suggestionLoading.clear();
      _suggestionErrors.clear();
      _result = null;
    });
  }

  void _dismissPopover() {
    setState(() => _hoveredWord = null);
  }

  void _showSuggestionPopover(String word) {
    showDialog(
      context: context,
      barrierColor: Colors.transparent,
      builder: (context) => ValueListenableBuilder<int>(
        valueListenable: _suggestionUpdateNotifier,
        builder: (context, _, __) {
          return Dialog(
            backgroundColor: Colors.transparent,
            elevation: 0,
            child: SuggestionPopover(
              term: word,
              suggestion: _suggestions[word],
              isLoading: _suggestionLoading[word] ?? false,
              error: _suggestionErrors[word],
              onAccept: () {
                Navigator.of(context).pop();
                _acceptSuggestion(word, _suggestions[word] ?? '');
              },
              onDismiss: () => Navigator.of(context).pop(),
            ),
          );
        },
      ),
    );
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
    final masculine = _getWords('masculine');
    final feminine = _getWords('feminine');

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
      final underlineColor =
          isMasculine ? const Color(0xFF8E7AB5) : const Color(0xFFB188B6);

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
                                      color: _getClassColor(_result!.detectedClass),
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
                          words: _getWords('masculine'),
                          bulletColor: const Color(0xFF8E7AB5),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: _CodedWordList(
                          title: 'Feminine Coded Words',
                          words: _getWords('feminine'),
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
          _suggestions.clear();
          _suggestionLoading.clear();
          _suggestionErrors.clear();
          _hoveredWord = null;
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
    return ElevatedButton(
      onPressed: _isRewriting ? null : _rewriteToNeutral,
      style: ButtonStyle(
        padding: MaterialStateProperty.all(
          const EdgeInsets.symmetric(horizontal: 80, vertical: 18),
        ),
        elevation: MaterialStateProperty.all(4),
        backgroundColor:
            MaterialStateProperty.resolveWith<Color>((states) {
          if (states.contains(MaterialState.disabled)) {
            return const Color(0xFFB188B6).withOpacity(0.6);
          }
          return states.contains(MaterialState.hovered)
              ? const Color(0xFF3A0E52)
              : const Color(0xFFB188B6);
        }),
        foregroundColor: MaterialStateProperty.resolveWith<Color>(
          (states) => states.contains(MaterialState.hovered)
              ? const Color(0xFFB188B6)
              : const Color(0xFF280647),
        ),
        shape: MaterialStateProperty.resolveWith<OutlinedBorder>(
          (states) => RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(30),
            side: BorderSide(
              color: states.contains(MaterialState.hovered)
                  ? const Color(0xFFB188B6)
                  : const Color(0xFF280647),
              width: 2.5,
            ),
          ),
        ),
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
  final Color bulletColor;

  const _CodedWordList({
    required this.title,
    required this.words,
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
                      shrinkWrap: true,
                      physics: const NeverScrollableScrollPhysics(),
                      itemCount: words.length,
                      itemBuilder: (context, index) {
                        return Padding(
                          padding: const EdgeInsets.symmetric(vertical: 4),
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
                                  words[index],
                                  style: GoogleFonts.poppins(
                                    fontSize: 12,
                                    color: const Color(0xFF333333),
                                    fontWeight: FontWeight.w500,
                                  ),
                                ),
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