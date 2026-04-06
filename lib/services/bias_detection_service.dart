import 'package:http/http.dart' as http;
import 'dart:convert';

class BiasDetectionResult {
  final String detectedClass;
  final Map<String, double> confidenceScores;
  final Map<String, List<String>> flaggedPhrases;
  final String accuracyNote;

  BiasDetectionResult({
    required this.detectedClass,
    required this.confidenceScores,
    required this.flaggedPhrases,
    required this.accuracyNote,
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
    );
  }
}

class BiasDetectionService {
  // Change this to your backend URL
  static const String baseUrl = 'http://localhost:5000';
  static const Duration timeout = Duration(seconds: 30);

  /// Detect bias in a single text
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

  /// Batch detect bias in multiple texts
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

  /// Check if backend is available
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
}
