import 'package:http/http.dart' as http;
import 'dart:convert';

class FlaggedWord {
  final String word;
  final String source;

  const FlaggedWord({
    required this.word,
    required this.source,
  });

  factory FlaggedWord.fromJson(Map<String, dynamic> json) {
    return FlaggedWord(
      word: json['word']?.toString() ?? '',
      source: json['source']?.toString() ?? '',
    );
  }

  @override
  String toString() => word;
}

class BiasDetectionResult {
  final String detectedClass;
  final Map<String, double> confidenceScores;

  final Map<String, List<FlaggedWord>> flaggedPhrases;

  final String accuracyNote;
  final String? modelVersion;

  BiasDetectionResult({
    required this.detectedClass,
    required this.confidenceScores,
    required this.flaggedPhrases,
    required this.accuracyNote,
    this.modelVersion,
  });

  factory BiasDetectionResult.fromJson(Map<String, dynamic> json) {
    final rawPhrases = json['flagged_phrases'] as Map<String, dynamic>? ?? {};

    final flaggedPhrases = <String, List<FlaggedWord>>{};

    for (final entry in rawPhrases.entries) {
      final key = entry.key.toString();
      final value = entry.value;

      if (value is List) {
        flaggedPhrases[key] = value.map((item) {
          if (item is Map<String, dynamic>) {
            return FlaggedWord.fromJson(item);
          }
          return FlaggedWord(word: item.toString(), source: '');
        }).toList();
      } else {
        flaggedPhrases[key] = [];
      }
    }

    return BiasDetectionResult(
      detectedClass: json['detected_class'] ?? 'unknown',
      confidenceScores: Map<String, double>.from(
        (json['confidence_scores'] as Map? ?? {}).map(
          (k, v) => MapEntry(k.toString(), (v as num).toDouble()),
        ),
      ),
      flaggedPhrases: flaggedPhrases,
      accuracyNote: json['accuracy_note'] ?? '',
      modelVersion: json['model_version'],
    );
  }

  List<String> wordStrings(String key) {
    return flaggedPhrases[key]?.map((fw) => fw.word).toList() ?? [];
  }
}

class GenderNeutralSuggestion {
  final String term;
  final String suggestion;
  final bool contextAware;

  GenderNeutralSuggestion({
    required this.term,
    required this.suggestion,
    required this.contextAware,
  });

  factory GenderNeutralSuggestion.fromJson(Map<String, dynamic> json) {
    return GenderNeutralSuggestion(
      term: json['term'] ?? '',
      suggestion: json['suggestion']?.toString().toLowerCase() ?? '',
      contextAware: json['context_aware'] ?? false,
    );
  }
}

class BiasDetectionService {
  static const String baseUrl = 'http://localhost:5000';
  static const Duration timeout = Duration(seconds: 30);

  static Future<BiasDetectionResult> detectBias(String text) async {
    try {
      final response = await http
          .post(
            Uri.parse('$baseUrl/detect'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({'text': text}),
          )
          .timeout(timeout);

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        return BiasDetectionResult.fromJson(data);
      } else {
        throw Exception('Error: ${response.statusCode} - ${response.body}');
      }
    } catch (e) {
      throw Exception('Failed to detect bias: $e');
    }
  }

  static Future<List<BiasDetectionResult>> batchDetect(
      List<String> texts) async {
    try {
      final response = await http
          .post(
            Uri.parse('$baseUrl/batch-detect'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({'texts': texts}),
          )
          .timeout(timeout);

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final results = data['results'] as List;
        return results
            .map((r) => BiasDetectionResult.fromJson(r))
            .toList();
      } else {
        throw Exception('Error: ${response.statusCode} - ${response.body}');
      }
    } catch (e) {
      throw Exception('Failed to batch detect: $e');
    }
  }

  static Future<GenderNeutralSuggestion> getContextAwareSuggestion(
    String term,
    String biasType, {
    String? context,
  }) async {
    try {
      final requestBody = {
        'term': term,
        'bias_type': biasType,
        if (context != null && context.isNotEmpty) 'context': context,
      };

      final response = await http
          .post(
            Uri.parse('$baseUrl/suggest'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode(requestBody),
          )
          .timeout(timeout);

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        return GenderNeutralSuggestion.fromJson(data);
      } else {
        throw Exception('Error: ${response.statusCode} - ${response.body}');
      }
    } catch (e) {
      throw Exception('Failed to get suggestion: $e');
    }
  }

  static Future<Map<String, dynamic>> rewriteJobAdToNeutral(String text) async {
    try {
      final response = await http
          .post(
            Uri.parse('$baseUrl/rewrite'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({'text': text}),
          )
          .timeout(const Duration(seconds: 60));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        return {
          'rewritten_text': data['rewritten_text'] ?? '',
          'detection_result': BiasDetectionResult.fromJson(data),
        };
      } else {
        throw Exception('Error: ${response.statusCode} - ${response.body}');
      }
    } catch (e) {
      throw Exception('Failed to rewrite job ad: $e');
    }
  }

  static Future<bool> healthCheck() async {
    try {
      final response = await http
          .get(Uri.parse('$baseUrl/health'))
          .timeout(const Duration(seconds: 5));
      return response.statusCode == 200;
    } catch (e) {
      return false;
    }
  }

  static Future<Map<String, dynamic>> getModelInfo() async {
    try {
      final response = await http
          .get(Uri.parse('$baseUrl/health'))
          .timeout(const Duration(seconds: 5));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        return data['model'] ?? {};
      } else {
        throw Exception('Failed to fetch model info: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('Failed to get model info: $e');
    }
  }
}