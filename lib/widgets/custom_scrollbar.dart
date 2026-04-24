import 'package:flutter/material.dart';

class CustomScrollbar extends StatefulWidget {
  final Widget child;

  final Color trackColor;
  final Color thumbColor;
  final double trackWidth;
  final double thumbThickness;
  final double radius;

  final Color arrowColor;
  final double iconSize;
  final double arrowInset;

  final ScrollPhysics scrollPhysics;

  const CustomScrollbar({
    super.key,
    required this.child,

    this.trackColor = const Color(0xFFF9E9FE),
    this.thumbColor = const Color(0xFFA984AE),
    this.trackWidth = 13.0,
    this.thumbThickness = 6.0,
    this.radius = 10.0,

    this.arrowColor = const Color(0xFFA984AE),
    this.iconSize = 20.0,
    this.arrowInset = .0,

    this.scrollPhysics = const AlwaysScrollableScrollPhysics(),
  });

  @override
  State<CustomScrollbar> createState() => _CustomScrollbarState();
}

class _CustomScrollbarState extends State<CustomScrollbar> {
  late final ScrollController _scrollController;

  static const int _scrollDuration = 180;
  static const double _scrollOffset = 90.0;
  static const double _arrowZoneHeight = 16.0;

  @override
  void initState() {
    super.initState();
    _scrollController = ScrollController();
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  void _scroll(double offset) {
    if (!_scrollController.hasClients) return;

    final targetOffset = (_scrollController.offset + offset).clamp(
      0.0,
      _scrollController.position.maxScrollExtent,
    );

    _scrollController.animateTo(
      targetOffset,
      duration: const Duration(milliseconds: _scrollDuration),
      curve: Curves.easeOut,
    );
  }


  Widget _buildTrack() {
    return Positioned(
      top: 0,
      bottom: 0,
      right: 0,
      child: Container(
        width: widget.trackWidth,
        decoration: BoxDecoration(
          color: widget.trackColor,
          borderRadius: BorderRadius.circular(widget.radius),
        ),
      ),
    );
  }


  Widget _buildScrollbar() {
    return RawScrollbar(
      controller: _scrollController,
      thumbVisibility: true,
      trackVisibility: false,
      thumbColor: widget.thumbColor,
      thickness: widget.thumbThickness,
      radius: Radius.circular(widget.radius),
      padding: EdgeInsets.only(
         top: _arrowZoneHeight,
         bottom: _arrowZoneHeight,
         right: (widget.trackWidth - widget.thumbThickness) / 2,
      ),
      child: SingleChildScrollView(
        controller: _scrollController,
        physics: widget.scrollPhysics,
        child: widget.child,
      ),
    );
  }


  Widget _buildArrow({required bool isUp}) {
    return Positioned(
      top: isUp ? 0.1 : null,
      bottom: isUp ? null : 0.1,
      right: (widget.trackWidth - widget.iconSize) / 2,
      child: GestureDetector(
        behavior: HitTestBehavior.translucent,
        onTap: () => _scroll(isUp ? -_scrollOffset : _scrollOffset),
        child: Icon(
          isUp ? Icons.arrow_drop_up : Icons.arrow_drop_down,
          size: widget.iconSize,
          color: widget.arrowColor,
        ),
      ),
    );
  }


  @override
  Widget build(BuildContext context) {
    return ScrollConfiguration(
      behavior: ScrollConfiguration.of(context).copyWith(scrollbars: false),
      child: Stack(
        alignment: Alignment.topRight,
        children: [
          _buildTrack(),
          _buildScrollbar(),
          _buildArrow(isUp: true),
          _buildArrow(isUp: false),
        ],
      ),
    );
  }
}
