"""
Interactive test runner for development.
Press Enter between steps to observe results.
"""
from typing import Callable, Any


class DemoRunner:
    """
    Runs interactive test steps with Enter-to-continue.

    Usage:
        demo = DemoRunner("MY TESTS")
        demo.header()

        result = await demo.step("Do something", my_async_fn, arg1, arg2)
        demo.show(f"Got: {result}")

        demo.footer(passed=True)
    """

    def __init__(self, name: str):
        self.name = name
        self.step_num = 0
        self.context = {}  # Shared state between steps

    async def step(self, description: str, fn: Callable, *args, **kwargs) -> Any:
        """
        Run a single test step interactively.

        Args:
            description: What this step does
            fn: Async function to run
            *args, **kwargs: Passed to fn

        Returns:
            Result of fn (also stored in self.context['last_result'])
        """
        self.step_num += 1
        input(f"\n[STEP {self.step_num}] {description} (Enter to run)")

        try:
            result = await fn(*args, **kwargs)
            print(f"  ✓ Done")
            self.context['last_result'] = result
            return result
        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            raise

    def show(self, message: str):
        """Print info without a step number."""
        print(f"  → {message}")

    def header(self):
        """Print test suite header."""
        print("\n" + "=" * 60)
        print(f"{self.name} (press Enter after each step)")
        print("=" * 60)

    def footer(self, passed: bool):
        """Print test suite footer."""
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED!" if passed else "TESTS FAILED")
        print("=" * 60)
