"""A log call whose `extra=` uses a name the logging module reserves raises KeyError at run time.

Such a call is invisible while loggers are silenced (the old test settings), and then breaks the request in
production. Two guards: the test settings now build every INFO record, and this scan checks the source directly.
"""

import ast
import logging
from pathlib import Path

from django.test import SimpleTestCase

RESERVED = set(vars(logging.makeLogRecord({}))) | {"message", "asctime"}
APPS = Path(__file__).resolve().parents[2]


def _extra_keys(call: ast.Call):
    for keyword in call.keywords:
        if keyword.arg == "extra" and isinstance(keyword.value, ast.Dict):
            for key in keyword.value.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    yield key.value, key.lineno


class LoggingExtraTests(SimpleTestCase):
    def test_no_log_call_uses_a_reserved_extra_key(self):
        offenders = []
        for path in sorted((APPS).rglob("*.py")):
            if "tests" in path.parts or "migrations" in path.parts:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    offenders += [
                        f"{path.relative_to(APPS)}:{line} uses {key!r}"
                        for key, line in _extra_keys(node)
                        if key in RESERVED
                    ]
        self.assertEqual(offenders, [])

    def test_the_scan_would_catch_the_mistake(self):
        call = ast.parse('logger.info("x", extra={"created": 1, "ok": 2})').body[0].value
        self.assertEqual([key for key, _ in _extra_keys(call) if key in RESERVED], ["created"])

    def test_application_loggers_really_build_info_records_in_tests(self):
        with self.assertRaises(KeyError):
            logging.getLogger("apps.core").info("probe", extra={"created": 1})
