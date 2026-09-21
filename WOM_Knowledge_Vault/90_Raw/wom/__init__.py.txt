"""
WOM – Weekly Operation Model
Global Supply Chain Planning & Simulation Tool
Version: v1r0m0
"""

__version__ = "1.0.0"
__author__ = "WOM Team"

from wom.config import WOMConfig
from wom.engine.simulator import WOMSimulator

__all__ = ["WOMConfig", "WOMSimulator"]
