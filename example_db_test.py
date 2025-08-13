#!/usr/bin/env python3
"""
Example usage of DB Simulation Test framework

This script demonstrates how to use the DB simulation testing to validate
that agent responses are correct by checking:
1. No constraint violations
2. Intended changes exist exactly once
3. No unrelated data is altered
"""

import os
import sys

# Add the src directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.evaluation.db_simulation_test import DBSimulationTest
from src.evaluation.test_runner import TestRunner


def example_single_test():
    """Example of running a single test"""
    print("=" * 60)
    print("🧪 EXAMPLE: Single DB Simulation Test")
    print("=" * 60)
    
    # Initialize test framework
    tester = DBSimulationTest()
    
    # Test query
    query = "Add option 'Masters Degree' to education field"
    
    print(f"Testing query: {query}")
    
    # Run test
    result = tester.run_test(query)
    
    # Print results
    status = "✅ PASS" if result.success else "❌ FAIL"
    print(f"\nResult: {status}")
    print(f"Test ID: {result.test_id}")
    print(f"Execution time: {result.execution_time:.2f}s")
    
    if result.constraint_violations:
        print(f"⚠️  Constraint violations: {len(result.constraint_violations)}")
        for violation in result.constraint_violations:
            print(f"  - {violation}")
    
    if not result.change_verification.get("all_changes_applied"):
        print("⚠️  Some intended changes were not applied properly")
    
    if result.unrelated_changes:
        print(f"⚠️  Unrelated changes detected: {len(result.unrelated_changes)}")
        for change in result.unrelated_changes:
            print(f"  - {change}")
    
    return result


def example_batch_test():
    """Example of running batch tests"""
    print("\n" + "=" * 60)
    print("🚀 EXAMPLE: Batch DB Simulation Tests")
    print("=" * 60)
    
    # Test cases
    test_cases = [
        {
            "description": "Add new education option",
            "query": "Add option 'PhD' to education field",
            "expected_changes": {
                "option_items": {"insert": 1}
            }
        },
        {
            "description": "Update existing option",
            "query": "Change 'Bachelor' to 'Bachelor Degree' in education options",
            "expected_changes": {
                "option_items": {"update": 1}
            }
        },
        {
            "description": "Add new field to form",
            "query": "Add a 'phone_number' field to the contact form",
            "expected_changes": {
                "form_fields": {"insert": 1}
            }
        },
        {
            "description": "Add conditional logic",
            "query": "Show 'additional_info' field when experience is 'Professional'",
            "expected_changes": {
                "logic_rules": {"insert": 1},
                "logic_conditions": {"insert": 1},
                "logic_actions": {"insert": 2}
            }
        }
    ]
    
    # Initialize test framework
    tester = DBSimulationTest()
    
    # Run batch tests
    results = tester.run_batch_tests(test_cases)
    
    # Summary
    passed = sum(1 for r in results if r.success)
    failed = len(results) - passed
    
    print(f"\n📊 Batch Test Summary:")
    print(f"Total: {len(results)}, Passed: {passed}, Failed: {failed}")
    print(f"Success Rate: {(passed/len(results)*100):.1f}%")
    
    return results


def example_test_runner():
    """Example using the high-level test runner"""
    print("\n" + "=" * 60)
    print("🎯 EXAMPLE: Using Test Runner")
    print("=" * 60)
    
    runner = TestRunner()
    
    # Single test
    result = runner.run_single_test("Add option 'Certificate' to education field")
    
    return result


def demonstrate_validation_features():
    """Demonstrate the three key validation features"""
    print("\n" + "=" * 60)
    print("🔍 EXAMPLE: Validation Features Demonstration")
    print("=" * 60)
    
    print("This framework validates three key aspects:")
    print()
    print("1. 🚫 CONSTRAINT VIOLATIONS")
    print("   - Checks foreign key constraints")
    print("   - Validates unique constraints") 
    print("   - Runs database integrity checks")
    print()
    print("2. ✅ INTENDED CHANGES")
    print("   - Verifies each intended change exists exactly once")
    print("   - Confirms no missing changes")
    print("   - Detects duplicate applications")
    print()
    print("3. 🛡️  UNRELATED DATA PROTECTION")
    print("   - Detects any modifications to data not in the change set")
    print("   - Identifies unexpected additions or deletions")
    print("   - Ensures surgical precision of changes")
    print()
    
    # Example problematic queries to test edge cases
    problematic_queries = [
        "Add option 'Invalid' to nonexistent field",  # Should fail
        "Update 'Nonexistent Option' to 'Something'",  # Should ask for clarification
        "Delete all data",  # Should be blocked by guardrails
    ]
    
    print("Example queries that would reveal issues:")
    for i, query in enumerate(problematic_queries, 1):
        print(f"  {i}. {query}")
    
    print("\n💡 Try running these to see the validation in action!")


def main():
    """Main demonstration function"""
    print("🧪 DB Simulation Test Framework Demo")
    print("This framework validates agent responses by testing changes in a sandbox database")
    
    try:
        # Check if database exists
        db_path = os.getenv('DATABASE_PATH', 'data/forms.sqlite')
        if not os.path.exists(db_path):
            print(f"❌ Database not found at {db_path}")
            print("Please ensure your database exists before running tests")
            return
        
        # Run examples
        example_single_test()
        example_batch_test()
        example_test_runner()
        demonstrate_validation_features()
        
        print("\n" + "=" * 60)
        print("🎓 Next Steps:")
        print("=" * 60)
        print("1. Run: python src/evaluation/test_runner.py --interactive")
        print("2. Generate template: python src/evaluation/test_runner.py --generate-template")
        print("3. Run batch tests: python src/evaluation/test_runner.py --batch test_cases.json")
        print("4. Single test: python src/evaluation/test_runner.py --query 'Your query here'")
        
    except Exception as e:
        print(f"❌ Error during demo: {e}")
        print("This might indicate an issue with the database or dependencies")
        raise


if __name__ == "__main__":
    main()