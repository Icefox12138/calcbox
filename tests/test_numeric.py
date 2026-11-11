import unittest
from unittest import mock

from calcbox import backends, backend_status, compute
from calcbox.contract import BackendUnavailable

BACKENDS = backend_status()


@unittest.skipUnless(BACKENDS["scipy"]["available"], "scipy not installed")
class TestSciPy(unittest.TestCase):
    def test_quad_cross_checks_against_sympy(self):
        out = compute("x^2", "quad", point="0", target="1")
        self.assertEqual(out["backend"], "scipy")
        self.assertAlmostEqual(out["result"], 1 / 3, places=6)
        self.assertFalse(out["disputed"])
        self.assertIsNotNone(out["cross_check"])
        self.assertAlmostEqual(out["cross_check"]["value"], 1 / 3, places=6)
        self.assertEqual(out["verification"]["method"], "quad_error")
        self.assertTrue(out["verification"]["ok"])

    def test_minimize(self):
        out = compute("(x-2)^2", "minimize", point="0")
        self.assertAlmostEqual(out["result"], 2.0, places=4)

    def test_root(self):
        out = compute("x^2-2", "root", point="1", target="2")
        self.assertAlmostEqual(out["result"], 2 ** 0.5, places=4)

    def test_disputed_propagates(self):
        fake = {"result": 1.0, "latex": "", "numeric": 1.0, "details": {},
                "disputed": True,
                "cross_check": {"backend": "sympy", "value": 2.0,
                                "difference": 1.0}}
        with mock.patch.object(backends, "_run_worker", return_value=fake):
            out = compute("x", "quad", point="0", target="1")
        self.assertTrue(out["disputed"])
        self.assertTrue(out["credentials"]["disputed"])
        self.assertEqual(out["cross_check"]["difference"], 1.0)


@unittest.skipUnless(BACKENDS["pint"]["available"], "pint not installed")
class TestPint(unittest.TestCase):
    def test_convert(self):
        out = compute("3 m", "convert", target="ft", backend="pint")
        self.assertAlmostEqual(out["numeric"], 9.8425, places=3)
        self.assertEqual(out["verification"]["method"], "unit_registry")

    def test_bad_unit_expression(self):
        with self.assertRaises(Exception):
            compute("3 m', 'x'", "convert", target="ft", backend="pint")


@unittest.skipUnless(BACKENDS["control"]["available"], "control not installed")
class TestControl(unittest.TestCase):
    def test_step_info(self):
        out = compute("", "step", backend="control",
                      data={"num": [1], "den": [1, 2, 1]})
        self.assertTrue(out["ok"])
        self.assertEqual(out["verification"]["method"], "step_info")
        self.assertIn("SteadyStateValue", out["details"])

    def test_bad_data(self):
        with self.assertRaises(Exception):
            compute("", "step", backend="control", data={"num": "x", "den": [1]})


class TestDispatch(unittest.TestCase):
    def test_unknown_operation_has_no_backend(self):
        from calcbox.contract import ComputeError
        with self.assertRaises(ComputeError):
            compute("x", "no-such-op")

    def test_pint_without_target_is_rejected(self):
        if not BACKENDS["pint"]["available"]:
            self.skipTest("pint not installed")
        from calcbox.contract import ComputeError
        with self.assertRaises(ComputeError):
            compute("3 m", "convert", backend="pint")


if __name__ == "__main__":
    unittest.main()
