import 'package:flutter/material.dart';

const List<String> kIndustries = [
  'Call Center',
  'BPO',
  'Public Service',
  'Education',
  'Computer/IT',
  'Retail and Trade',
  'Manufacturing',
  'Banking and Finance',
  'Healthcare',
  'Construction and Building',
  'Property and Real Estate',
];

const List<String> kTop10Industries = [
  'Call Center',
  'BPO',
  'Public Service',
  'Education',
  'Computer/IT',
  'Retail and Trade',
  'Manufacturing',
  'Banking and Finance',
  'Healthcare',
  'Construction and Building',
];

const List<String> kBiasTypes = [
  'Female-bias',
  'Male-bias',
];

class DashboardPage extends StatefulWidget {
  const DashboardPage({super.key});

  @override
  State<DashboardPage> createState() => _DashboardPageState();
}

class _DashboardPageState extends State<DashboardPage> {
  String _selectedIndustryTop = 'Public Service';
  String _selectedIndustryDist = 'Public Service';
  String _selectedBias = 'Female-bias';

  // Purple palette
  static const Color _purple = Color(0xFF7C3AED);
  static const Color _purpleMid = Color(0xFFA855F7);
  static const Color _purpleLight = Color(0xFFEDE9FE);
  static const Color _purpleSoft = Color(0xFFF3EDFB);
  static const Color _cardBg = Color(0xFFF5EFFE);

  Widget _buildDropdown({
    required String value,
    required List<String> items,
    required ValueChanged<String?> onChanged,
    bool dark = false,
  }) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 2),
      decoration: BoxDecoration(
        color: dark ? _purple : Colors.white,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: _purpleMid.withOpacity(0.4)),
      ),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<String>(
          value: value,
          icon: Icon(Icons.keyboard_arrow_down_rounded,
              color: dark ? Colors.white : const Color(0xFFF3A0E52), size: 20),
          style: TextStyle(
            color: dark ? Colors.white : const Color(0xFFF3A0E52),
            fontFamily: 'Poppins',
            fontSize: 13,
            fontWeight: FontWeight.w600,
          ),
          dropdownColor: dark ? const Color(0xFFF3A0E52) : Colors.white,
          borderRadius: BorderRadius.circular(10),
          items: items.map((item) {
            final isSelected = item == value;
            return DropdownMenuItem<String>(
              value: item,
              child: Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: isSelected
                    ? BoxDecoration(
                        //color: dark ? Colors.white24 : _purpleLight,
                        borderRadius: BorderRadius.circular(6),
                      )
                    : null,
                child: Text(
                  item,
                  style: TextStyle(
                    color: dark ? Colors.white : const Color(0xFFF3A0E52),
                    fontSize: 13,
                    fontWeight:
                        isSelected ? FontWeight.w700 : FontWeight.normal,
                  ),
                ),
              ),
            );
          }).toList(),
          onChanged: onChanged,
        ),
      ),
    );
  }

  Widget _buildBlankChart({double height = 180}) {
    return Container(
      height: height,
      decoration: BoxDecoration(
        color: const Color.fromARGB(255, 255, 255, 255),
        borderRadius: BorderRadius.circular(12),
      ),
    );
  }

  Widget _buildCard({required Widget child,  Color? color}) {
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: color ?? const Color(0xFFF9E9FE), 
        borderRadius: BorderRadius.circular(18),
        boxShadow: [
          BoxShadow(
            color: _purpleMid.withOpacity(0.08),
            blurRadius: 16,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: child,
    );
  }

  // ── Card 1: Gender Bias Over 10 Years ─────────────────────────────────────
  Widget _buildGenderBiasCard() {
    return _buildCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              const Expanded(
                child: Text(
                  'Gender Bias Over the Span of 10 years',
                  style: TextStyle(
                    fontFamily: 'Georgia',
                    fontSize: 15,
                    fontWeight: FontWeight.w700,
                    color: Color(0xFF3B1F5E),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              _buildDropdown(
                value: _selectedIndustryTop,
                items: kIndustries,
                onChanged: (v) =>
                    setState(() => _selectedIndustryTop = v!),
              ),
            ],
          ),
          const SizedBox(height: 20),
          _buildBlankChart(height: 385),
        ],
      ),
    );
  }

  // ── Card 2: Top 10 Industries Based on Job Ads Volume ─────────────────────
  Widget _buildTop10Card() {
    return _buildCard(
      color: const Color(0xFFF9F8FF),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header banner
          Container(
            width: double.infinity,
            padding:
                const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            decoration: BoxDecoration(
              color: _purple.withOpacity(0.09),
              borderRadius: BorderRadius.circular(8),
            ),
            child: const Text(
              'TOP 10 INDUSTRIES BASED ON JOB ADS VOLUME',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 10,
                fontWeight: FontWeight.w800,
                color: Color(0xFF280647),
                letterSpacing: 0.7,
              ),
            ),
          ),
          const SizedBox(height: 14),
          // Column labels
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 4),
            child: Row(
              children: const [
                SizedBox(width: 32),
                Expanded(
                  child: Text(
                    'Industry',
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w700,
                      color: Color(0xFF3B1F5E),
                    ),
                  ),
                ),
                Text(
                  'Volume',
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                    color: Color(0xFF3B1F5E),
                  ),
                ),
              ],
            ),
          ),
          const Divider(color: Color(0xFFD8C4F0), height: 16),
          // 10 industry rows with actual names
          ...List.generate(kTop10Industries.length, (i) {
            return Padding(
              padding:
                  const EdgeInsets.symmetric(vertical: 7, horizontal: 4),
              child: Row(
                children: [
                  // Rank badge
                  Container(
                    width: 24,
                    height: 24,
                    decoration: BoxDecoration(
                      color: _purpleLight,
                      borderRadius: BorderRadius.circular(6),
                    ),
                    alignment: Alignment.center,
                    child: Text(
                      '${i + 1}',
                      style: const TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.w700,
                        color: Color(0xFF280647),
                      ),
                    ),
                  ),
                  const SizedBox(width: 10),
                  // Actual industry name
                  Expanded(
                    child: Text(
                      kTop10Industries[i],
                      style: const TextStyle(
                        fontSize: 13,
                        color: Color(0xFF3B1F5E),
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  // Initial percentage
                  const Text(
                    '0%',
                    style: TextStyle(
                      fontSize: 13,
                      color: Color(0xFF280647),
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ),
            );
          }),
        ],
      ),
    );
  }

  // ── Card 3: Distribution of Gender Bias ───────────────────────────────────
  Widget _buildDistributionCard() {
    return _buildCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Expanded(
                child: Text(
                  'Distribution of Gender Bias',
                  style: TextStyle(
                    fontFamily: 'Georgia',
                    fontSize: 15,
                    fontWeight: FontWeight.w700,
                    color: Color(0xFF3B1F5E),
                  ),
                ),
              ),
              Row(
                children: [
                  const Icon(Icons.tune_rounded,
                      color: Color(0xFF7C3AED), size: 18),
                  const SizedBox(width: 8),
                  _buildDropdown(
                    value: _selectedIndustryDist,
                    items: kIndustries,
                    onChanged: (v) =>
                        setState(() => _selectedIndustryDist = v!),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 20),
          _buildBlankChart(height: 220),
        ],
      ),
    );
  }

  // ── Card 4: Ranking of Industries Based on Gender Bias ────────────────────
  Widget _buildRankingCard() {
    return _buildCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Expanded(
                child: Text(
                  'Ranking of Industries Based on Gender Bias',
                  style: TextStyle(
                    fontFamily: 'Georgia',
                    fontSize: 15,
                    fontWeight: FontWeight.w700,
                    color: Color(0xFF3B1F5E),
                  ),
                ),
              ),
              _buildDropdown(
                value: _selectedBias,
                items: kBiasTypes,
                onChanged: (v) => setState(() => _selectedBias = v!),
              ),
            ],
          ),
          const SizedBox(height: 20),
          _buildBlankChart(height: 220),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Container(
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
      child: SingleChildScrollView(
        padding: const EdgeInsets.symmetric(vertical: 24),
        child: Column(
          children: [
            // ── Row 1: Two fully separate, independent side-by-side cards ──
            Padding(
              padding:
                  const EdgeInsets.symmetric(horizontal: 24, vertical: 10),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    flex: 55,
                    child: _buildGenderBiasCard(),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    flex: 45,
                    child: _buildTop10Card(),
                  ),
                ],
              ),
            ),

            // ── Row 2: Distribution of Gender Bias ─────────────────────────
            Padding(
              padding:
                  const EdgeInsets.symmetric(horizontal: 24, vertical: 10),
              child: _buildDistributionCard(),
            ),

            // ── Row 3: Ranking of Industries ───────────────────────────────
            Padding(
              padding:
                  const EdgeInsets.symmetric(horizontal: 24, vertical: 10),
              child: _buildRankingCard(),
            ),

            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }
}