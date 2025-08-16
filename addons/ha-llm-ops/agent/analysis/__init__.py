"""Compatibility layer for legacy imports.

The refactored agent merges incident detection and analysis into a single
problem workflow implemented in :mod:`agent.problems`. This module re-exports
those interfaces so existing code importing ``agent.analysis`` continues to
work while the ecosystem migrates.
"""
from ..problems import ProblemLogger, monitor

__all__ = ["ProblemLogger", "monitor"]

