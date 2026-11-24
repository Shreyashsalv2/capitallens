"""CapitalLens: historical-simulation VaR, Expected Shortfall, stressed VaR, back-testing and
Basel 2.5 market-risk capital for an FX and energy trading book."""

from .engine import Config, analyse, what_if

__all__ = ["Config", "analyse", "what_if"]
__version__ = "1.0.0"
