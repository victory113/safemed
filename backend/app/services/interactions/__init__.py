"""Interaction checking.

The safety engine talks to an InteractionSource, never to a specific dataset.
Swapping the dataset means writing one new class - nothing else changes.
"""
from app.services.interactions.base import InteractionHit, InteractionSource
from app.services.interactions.ddinter import DDInterSource

__all__ = ["InteractionHit", "InteractionSource", "DDInterSource"]
