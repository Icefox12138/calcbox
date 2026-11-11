import importlib.util
import unittest

from calcbox import backend_status, compute
from calcbox.contract import BackendUnavailable, ComputeError

HAS_SYMPY = importlib.util.find_spec("sympy") is not None


class TestSurface(unittest.TestCase):
    def test_backends_reports_every_name(self):
        status = backend_status()
        self.assertEqual(set(status), {"sympy", "scipy", "pint", "control",
                                       "wolfram", "lean"})
        for name, st in status.items():
            self.assertIn("available", st, name)

    def test_external_backends_are_disabled_by_default(self):
        status = backend_status()
        self.assertFalse(status["wolfram"]["available"])
        self.assertIn("disabled", status["wolfram"].get("reason", ""))

    def test_unknown_backend_is_a_client_error(self):
        with self.assertRaises(ComputeError):
            compute("1+1", "simplify", backend="nope")

    def test_unavailable_backend_says_why(self):
        with self.assertRaises(BackendUnavailable):
            compute("1+1", "eval", backend="wolfram")


@unittest.skipUnless(HAS_SYMPY, "sympy not installed")
class TestSymbolic(unittest.TestCase):
    def test_integral_carries_verification(self):
        out = compute("x**2", "integrate")
        self.assertTrue(out["ok"])
        self.assertEqual(out["backend"], "sympy")
        self.assertIn("x**3", out["result"].replace(" ", ""))
        self.assertEqual(out["verification"]["method"], "differentiate-back")
        self.assertTrue(out["verification"]["passed"])

    def test_derivative(self):
        out = compute("x**3", "diff")
        self.assertIn("3*x**2", out["result"].replace(" ", ""))

    def test_value_is_numeric(self):
        out = compute("2+3*4", "value")
        self.assertEqual(out["numeric"], 14.0)

    def test_definite_integral_uses_target(self):
        out = compute("x", "integrate", target="0,1")
        self.assertIn("1/2", out["result"])

    def test_provenance_fields_present(self):
        out = compute("x+1", "simplify")
        for key in ("backend", "engine_version", "assumptions", "verification",
                    "input_sha256", "generated_at", "elapsed_ms", "sandbox"):
            self.assertIn(key, out, key)
        self.assertEqual(len(out["input_sha256"]), 64)
        self.assertEqual(out["sandbox"], "audit-only")

    def test_auto_inference_picks_sympy(self):
        out = compute("x**2", "factor")
        self.assertEqual(out["backend"], "sympy")


if __name__ == "__main__":
    unittest.main()
