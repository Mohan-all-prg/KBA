import sys
import time
from pathlib import Path

# Configure utf-8 encoding for Windows consoles safely
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.test_agent1_markdown import test_markdown_agent_create_and_update
from tests.test_agent2_database import test_database_agent_insert_update_and_audit
from tests.test_agent3_documentation import test_documentation_agent_generate_and_catalog
from tests.test_orchestrator import test_full_orchestrator_pipeline
from tests.test_api import test_api_endpoints
from tests.test_enhancements import test_all_enhancements
from tests.test_host import test_mcp_host_suite

def main():
    print("=" * 70)
    print("RUNNING MULTI-AGENT WORKFLOW TEST SUITE")
    print("=" * 70)

    tests = [
        ("Agent 1 (Markdown Agent)", test_markdown_agent_create_and_update),
        ("Agent 2 (Database Agent)", test_database_agent_insert_update_and_audit),
        ("Agent 3 (Documentation Agent)", test_documentation_agent_generate_and_catalog),
        ("Main Workflow Orchestrator", test_full_orchestrator_pipeline),
        ("Starlette Web & REST API", test_api_endpoints),
        ("Validation, Edit & Delete Enhancements", test_all_enhancements),
        ("MCP Host Mode & Tool Execution", test_mcp_host_suite),
    ]

    passed = 0
    start_time = time.time()

    for name, test_fn in tests:
        print(f"\n[TEST SUITE] {name}...")
        try:
            test_fn()
            passed += 1
            print(f"--> [PASS] {name}")
        except Exception as e:
            print(f"--> [FAIL] {name}: {e}")
            import traceback
            traceback.print_exc()

    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print(f"RESULTS: {passed}/{len(tests)} test suites passed in {elapsed:.2f}s")
    print("=" * 70)

    if passed == len(tests):
        print(f">>> ALL {len(tests)} TEST SUITES PASSED SUCCESSFULLY! <<<")
        return 0
    else:
        print(">>> SOME TESTS FAILED <<<")
        return 1

if __name__ == "__main__":
    sys.exit(main())
