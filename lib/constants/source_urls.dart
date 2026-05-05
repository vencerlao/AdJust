const Map<String, String?> kSourceUrls = {
  'Gaucher, Friesen & Kay (2011)':
      'https://ideas.wharton.upenn.edu/wp-content/uploads/2018/07/Gaucher-Friesen-Kay-2011.pdf',

  'BIAS Word Inventory — Konnikov et al. (2022)':
      'https://ray.yorksj.ac.uk/id/eprint/7555/1/BIAS%20Word%20Inventory%20%28Version%201%29.pdf',

  'Gender-Fair Language Primer — Kintanar (1998)':
      'https://library.pcw.gov.ph/wp-content/uploads/2020/12/Filipiniana-Gender-Fair-Language-A-Primer-1998.pdf',

  'EIGE Toolkit on Gender-sensitive Communication (2019)':
      'https://eige.europa.eu/sites/default/files/documents/20193925_mh0119609enn_pdf.pdf',

  'MCWC Accessible Gender and Sexual Orientation Inclusive Language':
      'https://www.moorparkcollege.edu/sites/moorparkcollege/files/media/pdf_document/2022/MCWC_accessible%20gender%20and%20sexual%20orientation%20inclusive%20langauge.pdf',

  'The Gender Dictionary – English Version (UNDP WACA, 2024)':
      'https://www.undp.org/africa/waca/publications/gender-dictionary',

  'UN Guidelines for gender-inclusive language in English':
      'https://www.un.org/en/gender-inclusive-language/guidelines.shtml',

  'UNESCO Gender-Neutral Guidelines':
      'https://unesdoc.unesco.org/ark:/48223/pf0000377299',

  'LinkedIn Talent Solutions / Cpl HR':
      'https://apastyle.apa.org/style-grammar-guidelines/bias-free-language',

  'LinkedIn Talent Solutions':
      'https://apastyle.apa.org/style-grammar-guidelines/bias-free-language',

  'Boston University Inclusive Language Editorial Style Guide':
      'https://www.bu.edu/brand/guidelines/editorial-style/inclusive-language/',

  // Internal source — no public URL, link behavior omitted
  'BUCGAD Feedback': null,
};

/// Resolves a URL for a given source string.
/// Handles pipe-delimited multi-source strings and partial key matches.
/// Returns null if no URL is found or the source is intentionally unlinked.
String? resolveSourceUrl(String source) {
  // Direct match first
  if (kSourceUrls.containsKey(source)) return kSourceUrls[source];

  // Partial match — handles cases like
  // "BIAS Word Inventory — Konnikov et al. (2022) | Gaucher, Friesen & Kay (2011)"
  for (final entry in kSourceUrls.entries) {
    if (entry.key != 'BUCGAD Feedback' && source.contains(entry.key)) {
      return entry.value;
    }
  }

  return null;
}

/// Splits a pipe-delimited source string into individual source keys,
/// each paired with its resolved URL.
/// Example input: "BIAS Word Inventory — Konnikov et al. (2022) | Gaucher, Friesen & Kay (2011)"
List<({String label, String? url})> splitSources(String rawSource) {
  final parts = rawSource
      .split(RegExp(r'\s*[|]\s*'))
      .map((s) => s.trim())
      .where((s) => s.isNotEmpty)
      .toList();

  return parts.map((part) {
    String? url;

    // Direct lookup
    if (kSourceUrls.containsKey(part)) {
      url = kSourceUrls[part];
    } else {
      // Partial match fallback
      for (final entry in kSourceUrls.entries) {
        if (entry.key != 'BUCGAD Feedback' && part.contains(entry.key)) {
          url = entry.value;
          break;
        }
      }
    }

    return (label: part, url: url);
  }).toList();
}
