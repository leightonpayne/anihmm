from __future__ import annotations

import importlib.util
import sys
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from rich.console import Console


def load_example():
    module_name = "processing_demo_test_module"
    sys.modules.pop(module_name, None)
    module_path = Path(__file__).resolve().parents[2] / "examples" / "processing_demo.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load the processing example module.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class ExampleWorkflowTests(unittest.TestCase):
    def test_demo_prints_completion_and_result_summary(self) -> None:
        module = load_example()
        output = StringIO()
        console = Console(file=output, force_terminal=False, width=100)

        with patch.multiple(module, WORK_SECONDS=0, DUMMY_HIT_COUNTS=(0, 2, 0, 3)):
            results = module.main(console)

        self.assertEqual(results, [0, 2, 0, 3])
        lines = output.getvalue().splitlines()
        self.assertIn("COMPLETE", ["".join(line.split()) for line in lines[:-3]])
        self.assertEqual(
            lines[-3:],
            ["Searched 4 HMMs", "2 HMMs produced hits", "5 total hits"],
        )
