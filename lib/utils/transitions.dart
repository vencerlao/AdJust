import 'package:flutter/material.dart';

class PageTransitions {
  static Route<T> go<T>(
    Widget child, {
    Duration duration = const Duration(milliseconds: 500),
  }) {
    return PageRouteBuilder<T>(
      pageBuilder: (context, animation, secondaryAnimation) => child,
      transitionDuration: duration,
      reverseTransitionDuration: duration,
      transitionsBuilder: (context, animation, secondaryAnimation, child) {
        const begin = Offset(0.0, 0.04);
        const end = Offset.zero;
        const curve = Curves.easeInOutCubic;

        final slideTween = Tween(begin: begin, end: end).chain(
          CurveTween(curve: curve),
        );

        final fadeTween = Tween<double>(begin: 0.0, end: 1.0).chain(
          CurveTween(curve: curve),
        );

        return FadeTransition(
          opacity: animation.drive(fadeTween),
          child: SlideTransition(
            position: animation.drive(slideTween),
            child: child,
          ),
        );
      },
    );
  }
}