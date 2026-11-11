import unittest

from calcbox import backend_status, compute
from calcbox.contract import BackendUnavailable, ComputeError

BACKENDS = backend_status()


class TestSymPy(unittest.TestCase):
    def test_diff(self):
        out = compute("x^2", "diff")
        self.assertEqual(out["backend"], "sympy")
        self.assertEqual(out["result"], "2*x")

    def test_forbidden(self):
        with self.assertRaises(ComputeError):
            compute("__import__('os')", "simplify")

    def test_backend_status_lists_operations(self):
        self.assertTrue(BACKENDS["sympy"]["available"])
        self.assertIn("diff", BACKENDS["sympy"]["operations"])

    def test_sandbox_marker(self):
        out = compute("x^2", "diff")
        self.assertEqual(out["sandbox"], "audit-only")
        self.assertEqual(out["credentials"]["sandbox"], "audit-only")

    def test_credentials_shape(self):
        out = compute("x^2", "diff")
        cred = out["credentials"]
        for key in ("backend", "engine_version", "input_sha256", "operation",
                    "assumptions", "verification", "disputed", "generated_at"):
            self.assertIn(key, cred)
        self.assertTrue(cred["verification"]["ok"])
        self.assertEqual(len(cred["input_sha256"]), 64)

    def test_integral_verifies_by_differentiating_back(self):
        out = compute("x^2", "integrate")
        self.assertIn("x**3", out["result"].replace(" ", ""))
        self.assertTrue(out["verification"]["ok"])
        self.assertEqual(out["verification"]["method"], "differentiate-back")

    def test_definite_integral(self):
        out = compute("x", "integrate", target="0,1")
        self.assertIn("1/2", out["result"])

    def test_solve_verifies_by_substitution(self):
        out = compute("x^2-1", "solve")
        self.assertTrue(out["verification"]["ok"])

    def test_value_is_numeric(self):
        out = compute("2+3*4", "value")
        self.assertEqual(out["numeric"], 14.0)

    def test_timeout(self):
        with self.assertRaises(ComputeError) as ctx:
            compute("exp(x^2)*sin(x)^10", "integrate", timeout=0.1)
        self.assertIn("timed out", str(ctx.exception))

    def test_unknown_backend(self):
        with self.assertRaises(ComputeError):
            compute("x", "diff", backend="nope")

    def test_external_disabled(self):
        for backend, op in (("wolfram", "eval"), ("lean", "check")):
            if not BACKENDS[backend]["available"]:
                with self.assertRaises(BackendUnavailable):
                    compute("1+1", op, backend=backend)

    def test_not_yet_ported_backends_say_so(self):
        for backend, op in (("scipy", "quad"), ("pint", "convert"),
                            ("control", "step")):
            if BACKENDS[backend]["available"]:
                with self.assertRaises(BackendUnavailable) as ctx:
                    compute("x", op, backend=backend,
                            data={"num": [1], "den": [1, 1]})
                self.assertIn("not ported", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
