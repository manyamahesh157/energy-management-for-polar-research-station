"""
PolarSync AI - Master Test Suite Runner
Runs unit tests across Physics Digital Twin, Deterministic Safety Shield,
Conformal Forecaster, and Controllers using Python standard library unittest.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.abspath("."))

from tests.test_twin import TestPhysicsTwin
from tests.test_safety_shield import TestSafetyShield
from tests.test_forecaster import TestForecaster
from tests.test_controllers import TestControllers

if __name__ == "__main__":
    print("=" * 70)
    print(" PolarSync AI (SIH26061) - Comprehensive Polar Test Suite")
    print(" Ministry of Earth Sciences | NCPOR | Team anvaya")
    print("=" * 70)
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestPhysicsTwin))
    suite.addTests(loader.loadTestsFromTestCase(TestSafetyShield))
    suite.addTests(loader.loadTestsFromTestCase(TestForecaster))
    suite.addTests(loader.loadTestsFromTestCase(TestControllers))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "=" * 70)
    if result.wasSuccessful():
        print(f" ALL {result.testsRun} POLAR TESTS PASSED (100% SUCCESS RATE)")
        print(" Physics Twin, Deterministic Safety Shield, Conformal Forecaster & Controllers Verified.")
        print("=" * 70)
        sys.exit(0)
    else:
        print(f" FAILED: {len(result.failures)} failures, {len(result.errors)} errors out of {result.testsRun} tests.")
        print("=" * 70)
        sys.exit(1)
