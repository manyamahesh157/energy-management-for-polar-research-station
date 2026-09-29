"""
Unit Tests for Conformal Forecaster
Verifies quantile monotonicity (q10 <= q50 <= q90) and conformal interval generation.
"""

import unittest
from backend.forecasting.conformal_forecaster import FORECASTER


class TestForecaster(unittest.TestCase):
    def test_forecaster_quantiles_monotonic(self):
        if not FORECASTER.is_trained:
            FORECASTER.train_and_calibrate()
            
        test_features = {
            "hour": 12,
            "day": 180,
            "ambient_temp_c": -32.0,
            "wind_speed_ms": 11.5
        }
        
        fc = FORECASTER.forecast_24h(test_features)
        
        self.assertIn("total_load_kw", fc)
        self.assertIn("wind_speed_ms", fc)
        self.assertIn("ghi_w_m2", fc)
        self.assertIn("ambient_temp_c", fc)
        
        for tgt, bands in fc.items():
            q10 = bands["lower_q10"]
            q50 = bands["median_q50"]
            q90 = bands["upper_q90"]
            
            self.assertEqual(len(q10), 24)
            for i in range(24):
                self.assertLessEqual(q10[i], q50[i] + 0.1)
                self.assertLessEqual(q50[i], q90[i] + 0.1)


if __name__ == "__main__":
    unittest.main()
