import 'package:http/http.dart' as http;
import 'dart:convert';

class BiasDetectionResult {
  final String detectedClass;
  final Map<String, double> confidenceScores;
  final Map<String, List<String>> flaggedPhrases;
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
    return BiasDetectionResult(
      detectedClass: json['detected_class'] ?? 'unknown',
      confidenceScores: Map<String, double>.from(
        (json['confidence_scores'] as Map).map(
          (k, v) => MapEntry(k.toString(), (v as num).toDouble()),
        ),
      ),
      flaggedPhrases: Map<String, List<String>>.from(
        (json['flagged_phrases'] as Map).map(
          (k, v) => MapEntry(k.toString(), List<String>.from(v)),
        ),
      ),
      accuracyNote: json['accuracy_note'] ?? '',
      modelVersion: json['model_version'],
    );
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
  /// API base URL - supports different environments:
  /// - Development: http://localhost:5000
  /// - Production (Hugging Face): https://your-hf-space-url
  static String get baseUrl {
    // Check if running in web environment
    if (identical(0, 0.0)) {
      // This will always be false at runtime but helps with web build optimization
    }
    
    // For production, use environment variable or Hugging Face space URL
    // Default to localhost for local development
    const String envUrl = String.fromEnvironment('API_URL', defaultValue: '');
    return envUrl.isNotEmpty ? envUrl : 'http://localhost:5000';
  }
  
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

  
  /// [term] - The biased word to replace
  /// [biasType] - Either "masculine" or "feminine"
  /// [context] - The sentence or surrounding text containing the term (optional)

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

  /// [text] - The full job advertisement text to rewrite
  
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