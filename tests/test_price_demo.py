import importlib.util
import math
import pathlib
import sys
import unittest


SCRIPT = pathlib.Path(__file__).parents[1] / "scripts" / "price_demo.py"
SPEC = importlib.util.spec_from_file_location("price_demo", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class PriceDemoTests(unittest.TestCase):
    def test_put_call_parity_local(self):
        result = MODULE.calculate(MODULE.Inputs())
        self.assertLess(abs(result["checks"]["put_call_parity_error"]), 1e-10)

    def test_higher_borrow_lowers_forward(self):
        low, _ = MODULE.equity_forward(MODULE.Inputs(borrow_bps=0))
        high, _ = MODULE.equity_forward(MODULE.Inputs(borrow_bps=600))
        self.assertLess(high, low)

    def test_composite_volatility_formula(self):
        i = MODULE.Inputs(settlement="composite", vol=0.30, fx_vol=0.10, equity_fx_corr=0.25)
        _, vol, _ = MODULE.settlement_terms(i)
        expected = math.sqrt(0.30**2 + 0.10**2 + 2 * 0.25 * 0.30 * 0.10)
        self.assertAlmostEqual(vol, expected)

    def test_invalid_dividend_rejected(self):
        with self.assertRaises(ValueError):
            MODULE.calculate(MODULE.Inputs(spot=1, dividend=2, dividend_day=1))

    def test_quote_exceeds_theoretical_for_client_buy(self):
        result = MODULE.calculate(MODULE.Inputs())
        self.assertGreater(
            result["waterfall"]["client_buy_quote_pct"],
            result["waterfall"]["theoretical_pct"],
        )


if __name__ == "__main__":
    unittest.main()
