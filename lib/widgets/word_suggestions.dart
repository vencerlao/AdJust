import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// Popover widget that displays gender-neutral suggestion for a biased term.
/// Used when hovering over underlined gender-coded words in the text field.
class SuggestionPopover extends StatelessWidget {
  final String term;
  final String? suggestion;
  final bool isLoading;
  final String? error;
  final VoidCallback onAccept;
  final VoidCallback onDismiss;

  const SuggestionPopover({
    required this.term,
    required this.suggestion,
    required this.isLoading,
    required this.error,
    required this.onAccept,
    required this.onDismiss,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 280,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: const Color(0xFFD4B5E8),
          width: 1.5,
        ),
        boxShadow: [
          BoxShadow(
            color: const Color(0xFF000000).withOpacity(0.15),
            blurRadius: 8,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Original term with strikethrough
          Text(
            'Original:',
            style: GoogleFonts.poppins(
              fontSize: 11,
              color: Colors.grey,
              fontWeight: FontWeight.w500,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            term,
            style: GoogleFonts.poppins(
              fontSize: 14,
              color: const Color(0xFF666666),
              fontWeight: FontWeight.w600,
              decoration: TextDecoration.lineThrough,
            ),
          ),
          const SizedBox(height: 12),

          // Suggestion or loading indicator
          Text(
            'Suggestion:',
            style: GoogleFonts.poppins(
              fontSize: 11,
              color: Colors.grey,
              fontWeight: FontWeight.w500,
            ),
          ),
          const SizedBox(height: 4),
          if (isLoading)
            const SizedBox(
              height: 24,
              child: Align(
                alignment: Alignment.centerLeft,
                child: SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    valueColor: AlwaysStoppedAnimation<Color>(
                      Color(0xFFD4B5E8),
                    ),
                  ),
                ),
              ),
            )
          else if (error != null)
            Text(
              error!,
              style: GoogleFonts.poppins(
                fontSize: 13,
                color: Colors.red,
                fontStyle: FontStyle.italic,
              ),
            )
          else
            Text(
              suggestion ?? 'No suggestion available',
              style: GoogleFonts.poppins(
                fontSize: 14,
                color: const Color(0xFF2D3436),
                fontWeight: FontWeight.w700,
              ),
            ),
          const SizedBox(height: 16),

          // Action buttons
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              ElevatedButton(
                onPressed: error == null && !isLoading ? onAccept : null,
                style: ButtonStyle(
                  backgroundColor: MaterialStateProperty.resolveWith<Color>(
                    (states) {
                      if (states.contains(MaterialState.disabled)) {
                        return const Color(0xFFD4B5E8).withOpacity(0.4);
                      }
                      return const Color(0xFFD4B5E8);
                    },
                  ),
                  foregroundColor: MaterialStateProperty.all<Color>(
                    const Color(0xFF280647),
                  ),
                  padding: MaterialStateProperty.all<EdgeInsets>(
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  ),
                  shape: MaterialStateProperty.all<RoundedRectangleBorder>(
                    RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(6),
                    ),
                  ),
                ),
                child: Text(
                  'Accept',
                  style: GoogleFonts.poppins(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
              OutlinedButton(
                onPressed: onDismiss,
                style: ButtonStyle(
                  side: MaterialStateProperty.all<BorderSide>(
                    const BorderSide(
                      color: Color(0xFF280647),
                      width: 1,
                    ),
                  ),
                  padding: MaterialStateProperty.all<EdgeInsets>(
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  ),
                  shape: MaterialStateProperty.all<RoundedRectangleBorder>(
                    RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(6),
                    ),
                  ),
                ),
                child: Text(
                  'Dismiss',
                  style: GoogleFonts.poppins(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: const Color(0xFF280647),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

