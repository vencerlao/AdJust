import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:csv/csv.dart';
import 'package:fl_chart/fl_chart.dart';

const Map<String, String> kIndustryToCsv = {
  'All Industries': 'ALL',
  'Call Center / BPO': 'call center/it enabled service/bpo',
  'Public Service': 'public service',
  'Education': 'education',
  'Computer/IT': 'computer it',
  'Retail and Trade': 'retail and trade',
  'Manufacturing': 'manufacturing',
  'Banking and Finance': 'banking and finance',
  'Healthcare': 'healthcare',
  'Construction and Building': 'construction and building',
  'Property and Real Estate': 'property and real estate',
};

const List<String> kIndustries = [
  'All Industries',
  'Call Center / BPO',
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

const List<String> kBiasTypes = ['Male-bias', 'Female-bias'];

class _TsPoint {
  final String industry;
  final int year;
  final String series;
  final double value;
  final int totalPostings;
  final double trendLine;
  final String mkTrend;
  final double mkTau;
  final double mkPvalue;
  final double mkSlope;
  final bool mkSignificant;

  _TsPoint({
    required this.industry,
    required this.year,
    required this.series,
    required this.value,
    required this.totalPostings,
    required this.trendLine,
    required this.mkTrend,
    required this.mkTau,
    required this.mkPvalue,
    required this.mkSlope,
    required this.mkSignificant,
  });
}

class _MkResult {
  final String industry;
  final String series;
  final String seriesLabel;
  final int totalPosts;
  final String trend;
  final double pValue;
  final double tau;
  final double sensSlope;
  final bool significant;

  _MkResult({
    required this.industry,
    required this.series,
    required this.seriesLabel,
    required this.totalPosts,
    required this.trend,
    required this.pValue,
    required this.tau,
    required this.sensSlope,
    required this.significant,
  });
}

class _DashboardData {
  final List<_TsPoint> timeSeries;
  final List<_MkResult> mkResults;

  _DashboardData({required this.timeSeries, required this.mkResults});

  static Future<_DashboardData> load() async {
    final tsRaw =
        await rootBundle.loadString('data/timeseries_with_trend.csv');
    final tsParsed =
        const CsvToListConverter(eol: '\n').convert(tsRaw, eol: '\n');
    final tsPoints = <_TsPoint>[];
    for (int i = 1; i < tsParsed.length; i++) {
      final r = tsParsed[i];
      if (r.length < 11) continue;
      tsPoints.add(_TsPoint(
        industry: r[0].toString().trim().toLowerCase(),
        year: int.tryParse(r[1].toString()) ?? 0,
        series: r[2].toString().trim(),
        value: double.tryParse(r[3].toString()) ?? 0.0,
        totalPostings: int.tryParse(r[4].toString()) ?? 0,
        trendLine: double.tryParse(r[5].toString()) ?? 0.0,
        mkTrend: r[6].toString().trim(),
        mkTau: double.tryParse(r[7].toString()) ?? 0.0,
        mkPvalue: double.tryParse(r[8].toString()) ?? 0.0,
        mkSlope: double.tryParse(r[9].toString()) ?? 0.0,
        mkSignificant: r[10].toString().trim().toLowerCase() == 'true',
      ));
    }

    final mkRaw =
        await rootBundle.loadString('data/mann_kendall_results.csv');
    final mkParsed =
        const CsvToListConverter(eol: '\n').convert(mkRaw, eol: '\n');
    final mkResults = <_MkResult>[];
    for (int i = 1; i < mkParsed.length; i++) {
      final r = mkParsed[i];
      if (r.length < 12) continue;
      mkResults.add(_MkResult(
        industry: r[0].toString().trim().toLowerCase(),
        series: r[1].toString().trim(),
        seriesLabel: r[2].toString().trim(),
        totalPosts: int.tryParse(r[3].toString()) ?? 0,
        trend: r[4].toString().trim(),
        pValue: double.tryParse(r[5].toString()) ?? 1.0,
        tau: double.tryParse(r[6].toString()) ?? 0.0,
        sensSlope: double.tryParse(r[7].toString()) ?? 0.0,
        significant: r[11].toString().trim().toLowerCase() == 'true',
      ));
    }

    return _DashboardData(timeSeries: tsPoints, mkResults: mkResults);
  }

  List<_TsPoint> getTs(String csvIndustry, String series) {
    return timeSeries
        .where((p) =>
            p.industry == csvIndustry.toLowerCase() && p.series == series)
        .toList()
      ..sort((a, b) => a.year.compareTo(b.year));
  }

  Map<String, int> get totalPostingsPerIndustry {
    final map = <String, int>{};
    for (final p in timeSeries.where((p) => p.series == 'masculine_pct')) {
      map[p.industry] = (map[p.industry] ?? 0) + p.totalPostings;
    }
    return map;
  }

  Map<String, double> get avgBiasPerIndustry {
    final mascSum = <String, double>{};
    final femSum = <String, double>{};
    final counts = <String, int>{};
    for (final p in timeSeries) {
      if (p.series == 'masculine_pct') {
        mascSum[p.industry] = (mascSum[p.industry] ?? 0) + p.value;
        counts[p.industry] = (counts[p.industry] ?? 0) + 1;
      } else if (p.series == 'feminine_pct') {
        femSum[p.industry] = (femSum[p.industry] ?? 0) + p.value;
      }
    }
    final bias = <String, double>{};
    for (final ind in mascSum.keys) {
      final n = counts[ind] ?? 1;
      bias[ind] = ((mascSum[ind] ?? 0) - (femSum[ind] ?? 0)) / n;
    }
    return bias;
  }

  _MkResult? getMkResult(String csvIndustry, String series) {
    try {
      return mkResults.firstWhere((r) =>
          r.industry == csvIndustry.toLowerCase() && r.series == series);
    } catch (_) {
      return null;
    }
  }
}

class DashboardPage extends StatefulWidget {
  const DashboardPage({super.key});

  @override
  State<DashboardPage> createState() => _DashboardPageState();
}

class _DashboardPageState extends State<DashboardPage> {
  String _selectedIndustryTop = 'Public Service';
  String _selectedIndustryDist = 'Public Service';
  String _selectedBias = 'Male-bias';

  bool _showMasculine = true;
  bool _showFeminine = true;
  bool _showNeutral = false;
  bool _showMaleRanking = true; 

  _DashboardData? _data;
  bool _loading = true;

  static const Color _purple      = Color(0xFF7C3AED);
  static const Color _purpleMid   = Color(0xFFA855F7);
  static const Color _purpleLight = Color(0xFFEDE9FE);

  static const Color _mascColor   = Color(0xFF8643CA);
  static const Color _femColor    = Color(0xFF4C167F);
  static const Color _neutColor   = Color(0xFF4A2947);
  static const Color _trendColor  = Color(0xFF2D1B4E);

  static const Color _rankGradStart = Color(0xFFD09AE0);
  static const Color _rankGradMid   = Color(0xFF8643CA);
  static const Color _rankGradEnd   = Color(0xFF4C167F);

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    final data = await _DashboardData.load();
    if (mounted) setState(() { _data = data; _loading = false; });
  }

  String _toCsv(String label) =>
      kIndustryToCsv[label] ?? label.toLowerCase();

  Widget _buildDropdown({
    required String value,
    required List<String> items,
    required ValueChanged<String?> onChanged,
  }) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 2),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: _purpleMid.withOpacity(0.4)),
      ),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<String>(
          value: value,
          icon: const Icon(Icons.keyboard_arrow_down_rounded,
              color: Color(0xFF7C3AED), size: 20),
          style: const TextStyle(
            color: Color(0xFF3B1F5E),
            fontFamily: 'Poppins',
            fontSize: 13,
            fontWeight: FontWeight.w600,
          ),
          dropdownColor: Colors.white,
          borderRadius: BorderRadius.circular(10),
          items: items.map((item) {
            return DropdownMenuItem<String>(
              value: item,
              child: Text(item,
                  style: const TextStyle(
                      color: Color(0xFF3B1F5E), fontSize: 13)),
            );
          }).toList(),
          onChanged: onChanged,
        ),
      ),
    );
  }

  Widget _buildCard({required Widget child, Color? color}) {
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

  Widget _legendDot(Color color, String label) {
    return Row(children: [
      Container(width: 10, height: 10,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
      const SizedBox(width: 5),
      Text(label,
          style: const TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: Color(0xFF3B1F5E))),
      const SizedBox(width: 12),
    ]);
  }

  Widget _mkBadge(_MkResult? mk) {
    if (mk == null) return const SizedBox.shrink();
    final sig = mk.significant;
    final trendLabel = mk.trend == 'no trend'
        ? 'No Trend'
        : mk.trend[0].toUpperCase() + mk.trend.substring(1);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: sig ? _purple.withOpacity(0.12) : Colors.grey.withOpacity(0.1),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
            color: sig ? _purple.withOpacity(0.4) : Colors.grey.withOpacity(0.3)),
      ),
      child: Text(
        '$trendLabel  τ=${mk.tau.toStringAsFixed(2)}  p=${mk.pValue.toStringAsFixed(3)}${sig ? ' ✓' : ''}',
        style: TextStyle(
          fontSize: 10,
          fontWeight: FontWeight.w600,
          color: sig ? _purple : Colors.grey[600],
        ),
      ),
    );
  }

  Widget _seriesToggle({
    required bool active,
    required Color activeColor,
    required String label,
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
          color: active
              ? activeColor.withOpacity(0.18)
              : Colors.grey.withOpacity(0.08),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: active
                ? activeColor.withOpacity(0.7)
                : Colors.grey.withOpacity(0.3),
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 8, height: 8,
              decoration: BoxDecoration(
                color: active ? activeColor : Colors.grey,
                shape: BoxShape.circle,
              ),
            ),
            const SizedBox(width: 5),
            Text(
              label,
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w600,
                color: active ? activeColor : Colors.grey[500],
              ),
            ),
            const SizedBox(width: 4),
            Icon(
              active
                  ? Icons.visibility_rounded
                  : Icons.visibility_off_rounded,
              size: 13,
              color: active ? activeColor : Colors.grey[400],
            ),
          ],
        ),
      ),
    );
  }

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
                onChanged: (v) {
                  if (v == null) return;
                  setState(() => _selectedIndustryTop = v);
                },
              ),
            ],
          ),
          const SizedBox(height: 12),

          if (_loading)
            const SizedBox(
                height: 385,
                child: Center(child: CircularProgressIndicator()))
          else
            _buildLineChart(),
        ],
      ),
    );
  }

  Widget _buildLineChart() {
    final csvInd = _toCsv(_selectedIndustryTop);
    final mascPts = _data!.getTs(csvInd, 'masculine_pct');
    final femPts  = _data!.getTs(csvInd, 'feminine_pct');
    final neutPts = _data!.getTs(csvInd, 'neutral_pct');

    if (mascPts.isEmpty) {
      return const SizedBox(height: 385,
          child: Center(child: Text('No data available')));
    }

    final years = mascPts.map((p) => p.year).toList();
    const minY = 0.0;

    final visiblePts = <double>[
      if (_showMasculine) ...mascPts.map((p) => p.value),
      if (_showFeminine)  ...femPts.map((p) => p.value),
      if (_showNeutral)   ...neutPts.map((p) => p.value),
    ];
    final maxVal = visiblePts.isEmpty
        ? 30.0
        : visiblePts.fold<double>(0, (m, v) => v > m ? v : m);
    final maxY = ((maxVal + 5) / 5).ceil() * 5.0;

    List<FlSpot> toSpots(List<_TsPoint> pts) =>
        pts.asMap().entries
            .map((e) => FlSpot(e.key.toDouble(), e.value.value))
            .toList();

    final bars = <LineChartBarData>[
      if (_showMasculine)
        LineChartBarData(
          spots: toSpots(mascPts),
          isCurved: true,
          curveSmoothness: 0.3,
          color: _mascColor,
          barWidth: 2.5,
          dotData: FlDotData(
            show: true,
            getDotPainter: (_, __, ___, ____) => FlDotCirclePainter(
                radius: 3.5, color: _mascColor,
                strokeWidth: 1.5, strokeColor: Colors.white),
          ),
          belowBarData: BarAreaData(show: false),
        ),
      if (_showFeminine)
        LineChartBarData(
          spots: toSpots(femPts),
          isCurved: true,
          curveSmoothness: 0.3,
          color: _femColor,
          barWidth: 2.5,
          dotData: FlDotData(
            show: true,
            getDotPainter: (_, __, ___, ____) => FlDotCirclePainter(
                radius: 3.5, color: _femColor,
                strokeWidth: 1.5, strokeColor: Colors.white),
          ),
          belowBarData: BarAreaData(show: false),
        ),
      if (_showNeutral)
        LineChartBarData(
          spots: toSpots(neutPts),
          isCurved: true,
          curveSmoothness: 0.3,
          color: _neutColor,
          barWidth: 2.5,
          dotData: FlDotData(
            show: true,
            getDotPainter: (_, __, ___, ____) => FlDotCirclePainter(
                radius: 3.5, color: _neutColor,
                strokeWidth: 1.5, strokeColor: Colors.white),
          ),
          belowBarData: BarAreaData(show: false),
        ),
    ];

    final tooltipLabels = <String>[
      if (_showMasculine) 'Masculine',
      if (_showFeminine)  'Feminine',
      if (_showNeutral)   'Neutral',
    ];
    final tooltipColors = <Color>[
      if (_showMasculine) _mascColor,
      if (_showFeminine)  _femColor,
      if (_showNeutral)   _neutColor,
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            _seriesToggle(
              active: _showMasculine,
              activeColor: _mascColor,
              label: 'Masculine',
              onTap: () => setState(() => _showMasculine = !_showMasculine),
            ),
            const SizedBox(width: 8),
            _seriesToggle(
              active: _showFeminine,
              activeColor: _femColor,
              label: 'Feminine',
              onTap: () => setState(() => _showFeminine = !_showFeminine),
            ),
            const Spacer(),
            _seriesToggle(
              active: _showNeutral,
              activeColor: _neutColor,
              label: 'Neutral',
              onTap: () => setState(() => _showNeutral = !_showNeutral),
            ),
          ],
        ),
        const SizedBox(height: 14),

        SizedBox(
          height: 452,
          child: bars.isEmpty
              ? const Center(
                  child: Text('No series selected',
                      style: TextStyle(
                          color: Color(0xFF3B1F5E),
                          fontSize: 13,
                          fontWeight: FontWeight.w500)))
              : LineChart(
                  LineChartData(
                    minY: minY,
                    maxY: maxY,
                    gridData: FlGridData(
                      show: true,
                      drawVerticalLine: false,
                      getDrawingHorizontalLine: (_) => FlLine(
                          color: Colors.grey.withOpacity(0.15),
                          strokeWidth: 1),
                    ),
                    borderData: FlBorderData(
                      show: true,
                      border: Border(
                        bottom: BorderSide(
                            color: Colors.grey.withOpacity(0.3)),
                        left: BorderSide(
                            color: Colors.grey.withOpacity(0.3)),
                      ),
                    ),
                    titlesData: FlTitlesData(
                      bottomTitles: AxisTitles(
                        sideTitles: SideTitles(
                          showTitles: true,
                          interval: 1,
                          getTitlesWidget: (val, _) {
                            final idx = val.toInt();
                            if (idx < 0 || idx >= years.length) {
                              return const SizedBox.shrink();
                            }
                            return Padding(
                              padding: const EdgeInsets.only(top: 6),
                              child: Text('${years[idx]}',
                                  style: const TextStyle(
                                      fontSize: 11,
                                      fontWeight: FontWeight.w600,
                                      color: Color(0xFF3B1F5E))),
                            );
                          },
                        ),
                      ),
                      leftTitles: AxisTitles(
                        sideTitles: SideTitles(
                          showTitles: true,
                          interval: 20,
                          reservedSize: 40,
                          getTitlesWidget: (val, _) => Text(
                            '${val.toInt()}%',
                            style: const TextStyle(
                                fontSize: 11,
                                fontWeight: FontWeight.w600,
                                color: Color(0xFF3B1F5E)),
                          ),
                        ),
                      ),
                      topTitles: const AxisTitles(
                          sideTitles: SideTitles(showTitles: false)),
                      rightTitles: const AxisTitles(
                          sideTitles: SideTitles(showTitles: false)),
                    ),
                    lineTouchData: LineTouchData(
                      touchTooltipData: LineTouchTooltipData(
                        getTooltipColor: (_) => Colors.white,
                        tooltipBorder:
                            BorderSide(color: _purple.withOpacity(0.3)),
                        getTooltipItems: (spots) =>
                            spots.asMap().entries.map((e) {
                          final idx = e.key;
                          final s = e.value;
                          final label = idx < tooltipLabels.length
                              ? tooltipLabels[idx]
                              : '';
                          final col = idx < tooltipColors.length
                              ? tooltipColors[idx]
                              : _purple;
                          return LineTooltipItem(
                            '$label: ${s.y.toStringAsFixed(1)}%',
                            TextStyle(
                                color: col,
                                fontSize: 11,
                                fontWeight: FontWeight.w600),
                          );
                        }).toList(),
                      ),
                    ),
                    lineBarsData: bars,
                  ),
                ),
        ),
      ],
    );
  }

  Widget _buildTop10Card() {
    final totals = _data?.totalPostingsPerIndustry ?? {};
    final ranked = kIndustryToCsv.entries
        .where((e) => e.value != 'ALL')
        .map((e) => MapEntry(e.key, totals[e.value] ?? 0))
        .toList()
      ..sort((a, b) => b.value.compareTo(a.value));

    final grandTotal = ranked.fold<int>(0, (s, e) => s + e.value);

    return _buildCard(
      color: const Color(0xFFF9F8FF),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
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
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 4),
            child: Row(
              children: const [
                SizedBox(width: 32),
                Expanded(
                  child: Text('Industry',
                      style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w700,
                          color: Color(0xFF3B1F5E))),
                ),
                Text('Volume',
                    style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                        color: Color(0xFF3B1F5E))),
              ],
            ),
          ),
          const Divider(color: Color(0xFFD8C4F0), height: 16),

          if (_loading)
            const Center(child: CircularProgressIndicator())
          else
            ...ranked.take(10).toList().asMap().entries.map((entry) {
              final i = entry.key;
              final name = entry.value.key;
              final count = entry.value.value;
              final pct = grandTotal > 0
                  ? (count / grandTotal * 100).toStringAsFixed(1)
                  : '0.0';

              return Padding(
                padding:
                    const EdgeInsets.symmetric(vertical: 7, horizontal: 4),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Container(
                          width: 24, height: 24,
                          decoration: BoxDecoration(
                            color: _purpleLight,
                            borderRadius: BorderRadius.circular(6),
                          ),
                          alignment: Alignment.center,
                          child: Text('${i + 1}',
                              style: const TextStyle(
                                  fontSize: 10,
                                  fontWeight: FontWeight.w700,
                                  color: Color(0xFF280647))),
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Text(name,
                              style: const TextStyle(
                                  fontSize: 12,
                                  color: Color(0xFF3B1F5E),
                                  fontWeight: FontWeight.w500)),
                        ),
                        Text(
                          '${count.toString().replaceAllMapped(RegExp(r'(\d{1,3})(?=(\d{3})+(?!\d))'), (m) => '${m[1]},')}  ($pct%)',
                          style: const TextStyle(
                              fontSize: 12,
                              color: Color(0xFF280647),
                              fontWeight: FontWeight.w600),
                        ),
                      ],
                    ),
                    const SizedBox(height: 5),
                    ClipRRect(
                      borderRadius: BorderRadius.circular(4),
                      child: LinearProgressIndicator(
                        value: grandTotal > 0 ? count / grandTotal : 0,
                        minHeight: 5,
                        backgroundColor: _purpleLight,
                        valueColor:
                            AlwaysStoppedAnimation<Color>(_purpleMid),
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
                    onChanged: (v) {
                      if (v == null) return;
                      setState(() => _selectedIndustryDist = v);
                    },
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 16),
          if (_loading)
            const SizedBox(height: 220,
                child: Center(child: CircularProgressIndicator()))
          else
            _buildStackedBarChart(),
        ],
      ),
    );
  }

  Widget _buildStackedBarChart() {
    final csvInd = _toCsv(_selectedIndustryDist);
    final mascPts = _data!.getTs(csvInd, 'masculine_pct');
    final femPts  = _data!.getTs(csvInd, 'feminine_pct');
    final neutPts = _data!.getTs(csvInd, 'neutral_pct');

    if (mascPts.isEmpty) {
      return const SizedBox(height: 220,
          child: Center(child: Text('No data available')));
    }

    final years = mascPts.map((p) => p.year).toList();

    final barGroups = List.generate(mascPts.length, (i) {
      final masc = mascPts[i].value;
      final fem  = femPts.length > i ? femPts[i].value : 0.0;
      final neut = neutPts.length > i ? neutPts[i].value : 0.0;

      return BarChartGroupData(
        x: i,
        barRods: [
          BarChartRodData(
            toY: masc + fem + neut,
            width: 32, 
            borderRadius: const BorderRadius.vertical(top: Radius.circular(4)),
            rodStackItems: [
              BarChartRodStackItem(0, fem, const Color(0xFF9666A5)),
              BarChartRodStackItem(fem, fem + masc, const Color(0xFFD09AE0)),
              BarChartRodStackItem(fem + masc, fem + masc + neut, _neutColor),
            ],
          ),
        ],
      );
    });

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(children: [
          _legendDot(const Color(0xFFD09AE0), 'Masculine'),
          _legendDot(const Color(0xFF9666A5), 'Feminine'),
          _legendDot(_neutColor, 'Neutral'),
        ]),
        const SizedBox(height: 10),
        SizedBox(
          height: 350,
          child: BarChart(
            BarChartData(
              maxY: 100,
              barGroups: barGroups,
              gridData: FlGridData(
                show: true,
                drawVerticalLine: false,
                getDrawingHorizontalLine: (_) => FlLine(
                    color: Colors.grey.withOpacity(0.15), strokeWidth: 1),
              ),
              borderData: FlBorderData(
                show: true,
                border: Border(
                  bottom: BorderSide(color: Colors.grey.withOpacity(0.3)),
                  left: BorderSide(color: Colors.grey.withOpacity(0.3)),
                ),
              ),
              titlesData: FlTitlesData(
                bottomTitles: AxisTitles(
                  sideTitles: SideTitles(
                    showTitles: true,
                    getTitlesWidget: (val, _) {
                      final idx = val.toInt();
                      if (idx < 0 || idx >= years.length) {
                        return const SizedBox.shrink();
                      }
                      return Padding(
                        padding: const EdgeInsets.only(top: 6),
                        child: Text('${years[idx]}',
                            style: const TextStyle(
                                fontSize: 11,
                                fontWeight: FontWeight.w600,
                                color: Color(0xFF3B1F5E))),
                      );
                    },
                  ),
                ),
                leftTitles: AxisTitles(
                  sideTitles: SideTitles(
                    showTitles: true,
                    interval: 25,
                    reservedSize: 40,
                    getTitlesWidget: (val, _) => Text(
                      '${val.toInt()}%',
                      style: const TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                          color: Color(0xFF3B1F5E)),
                    ),
                  ),
                ),
                topTitles: const AxisTitles(
                    sideTitles: SideTitles(showTitles: false)),
                rightTitles: const AxisTitles(
                    sideTitles: SideTitles(showTitles: false)),
              ),
              barTouchData: BarTouchData(
                touchTooltipData: BarTouchTooltipData(
                  getTooltipColor: (_) => Colors.white,
                  tooltipBorder:
                      BorderSide(color: _purple.withOpacity(0.3)),
                  getTooltipItem: (group, groupIdx, rod, rodIdx) {
                    final y = years[groupIdx];
                    final m = mascPts[groupIdx].value;
                    final f = femPts.length > groupIdx
                        ? femPts[groupIdx].value
                        : 0.0;
                    final n = neutPts.length > groupIdx
                        ? neutPts[groupIdx].value
                        : 0.0;
                    return BarTooltipItem(
                      '$y\nMasc: ${m.toStringAsFixed(1)}%\nFem: ${f.toStringAsFixed(1)}%\nNeut: ${n.toStringAsFixed(1)}%',
                      const TextStyle(
                          fontSize: 11,
                          color: Color(0xFF3B1F5E),
                          fontWeight: FontWeight.w500),
                    );
                  },
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }

Widget _buildRankingCard() {
  return _buildCard(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                _showMaleRanking
                    ? 'Top Industries — Male-Coded Job Ads'
                    : 'Top Industries — Female-Coded Job Ads',
                style: const TextStyle(
                  fontFamily: 'Georgia',
                  fontSize: 15,
                  fontWeight: FontWeight.w700,
                  color: Color(0xFF3B1F5E),
                ),
              ),
            ),
            _buildDropdown(
              value: _showMaleRanking ? 'Male-Coded' : 'Female-Coded',
              items: ['Male-Coded', 'Female-Coded'],
              onChanged: (v) {
                if (v == null) return;
                setState(() => _showMaleRanking = v == 'Male-Coded');
              },
            ),
          ],
        ),
        const SizedBox(height: 20),
        if (_loading)
          const SizedBox(
              height: 400,
              child: Center(child: CircularProgressIndicator()))
        else
          _buildRankingBars(),
      ],
    ),
  );
}

Widget _buildRankingBars() {
  final industries = kIndustryToCsv.entries
      .where((e) => e.value != 'ALL')
      .toList();

  final mascAvg = <String, double>{};
  final femAvg  = <String, double>{};

  for (final ind in industries) {
    final csvKey  = ind.value;
    final mascPts = _data!.getTs(csvKey, 'masculine_pct');
    final femPts  = _data!.getTs(csvKey, 'feminine_pct');

    if (mascPts.isNotEmpty) {
      mascAvg[ind.key] = mascPts.map((p) => p.value).reduce((a, b) => a + b)
          / mascPts.length;
    }
    if (femPts.isNotEmpty) {
      femAvg[ind.key] = femPts.map((p) => p.value).reduce((a, b) => a + b)
          / femPts.length;
    }
  }

  final ranked = industries
      .map((e) => MapEntry(e.key,
          _showMaleRanking
              ? (mascAvg[e.key] ?? 0.0)
              : (femAvg[e.key] ?? 0.0)))
      .toList()
    ..sort((a, b) => b.value.compareTo(a.value));

  return _buildRankSection(ranked, isMale: _showMaleRanking);
}

Widget _buildRankSection(List<MapEntry<String, double>> items, {required bool isMale}) {
  final maxVal = items.isEmpty ? 1.0 : items.first.value;

final gradientColors = isMale
    ? const [
        Color(0xFF4A2947), 
        Color(0xFF573454),
        Color(0xFF643F61),
        Color(0xFF714A6E),
        Color(0xFF7E557B),
        Color(0xFF8B6088),
        Color(0xFF986B95),
        Color(0xFFA576A2),
        Color(0xFFB281AF),
        Color(0xFFBF8CBC), 
      ]
    : const [
        Color(0xFF3A0E52),
        Color(0xFF471A60),
        Color(0xFF54266E),
        Color(0xFF61327C),
        Color(0xFF6E3E8A),
        Color(0xFF7B4A98),
        Color(0xFF8856A6),
        Color(0xFF9562B4),
        Color(0xFFA26EC2),
        Color(0xFFAF7AD0), 
      ];

  return Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: items.take(10).toList().asMap().entries.map((entry) {
      final rank    = entry.key;
      final name    = entry.value.key;
      final avg     = entry.value.value;
      final barFrac = maxVal == 0 ? 0.0 : avg / maxVal;
      final display = '${avg.toStringAsFixed(1)}%';
      final color   = gradientColors[rank.clamp(0, gradientColors.length - 1)];

      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 7),
        child: Row(
          children: [
            SizedBox(
              width: 180,
              child: Text(
                name,
                style: const TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: Color(0xFF3B1F5E),
                ),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: LayoutBuilder(
                builder: (context, constraints) {
                  final barWidth = constraints.maxWidth * barFrac.clamp(0.0, 1.0);
                  return Container(
                    height: 22,
                    decoration: BoxDecoration(
                      color: Colors.grey.withOpacity(0.08),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Align(
                      alignment: Alignment.centerLeft,
                      child: Container(
                        width: barWidth,
                        height: 22,
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(6),
                          color: color,
                        ),
                      ),
                    ),
                  );
                },
              ),
            ),
            const SizedBox(width: 10),
            SizedBox(
              width: 44,
              child: Text(
                display,
                textAlign: TextAlign.right,
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w700,
                  color: color,
                ),
              ),
            ),
          ],
        ),
      );
    }).toList(),
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
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 10),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(flex: 65, child: _buildGenderBiasCard()),
                  const SizedBox(width: 16),
                  Expanded(flex: 35, child: _buildTop10Card()),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 10),
              child: _buildDistributionCard(),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 10),
              child: _buildRankingCard(),
            ),
            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }
}