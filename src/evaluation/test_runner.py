#!/usr/bin/env python3
"""
DB Simulation Test Runner

This script provides a command-line interface and programmatic API 
for running DB simulation tests to validate agent responses.

Usage:
    python test_runner.py --query "Add option 'Graduate' to education field"
    python test_runner.py --batch test_cases.json
    python test_runner.py --interactive
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict, Any
import tabulate

from .db_simulation_test import DBSimulationTest, TestResult


class TestRunner:
    """Test runner for DB simulation tests"""
    
    def __init__(self, db_path: str = None, output_dir: str = "test_results"):
        self.test_framework = DBSimulationTest(db_path, output_dir)
    
    def run_single_test(self, query: str, expected_changes: Dict[str, Any] = None) -> TestResult:
        """Run a single test"""
        print(f"\n🔍 Testing query: {query}")
        print("=" * 60)
        
        result = self.test_framework.run_test(query, expected_changes)
        
        self._print_test_result(result)
        return result
    
    def run_batch_tests(self, test_cases: List[Dict[str, Any]]) -> List[TestResult]:
        """Run batch tests from a list of test cases"""
        print(f"\n🚀 Running batch tests ({len(test_cases)} test cases)")
        print("=" * 60)
        
        results = self.test_framework.run_batch_tests(test_cases)
        
        self._print_batch_summary(results)
        return results
    
    def run_batch_from_file(self, file_path: str) -> List[TestResult]:
        """Run batch tests from a JSON file"""
        try:
            with open(file_path, 'r') as f:
                test_cases = json.load(f)
            
            if not isinstance(test_cases, list):
                test_cases = [test_cases]
            
            return self.run_batch_tests(test_cases)
            
        except FileNotFoundError:
            print(f"❌ Test file not found: {file_path}")
            return []
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in test file: {e}")
            return []
    
    def run_interactive_mode(self):
        """Run interactive testing mode"""
        print("\n🎯 Interactive DB Simulation Test Mode")
        print("=" * 60)
        print("Enter queries to test (type 'quit' to exit, 'help' for commands)")
        
        while True:
            try:
                query = input("\nTest query > ").strip()
                
                if query.lower() in ['quit', 'exit', 'q']:
                    break
                elif query.lower() == 'help':
                    self._print_help()
                    continue
                elif not query:
                    continue
                
                self.run_single_test(query)
                
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
    
    def _print_test_result(self, result: TestResult):
        """Print detailed test result"""
        status_icon = "✅" if result.success else "❌"
        print(f"\n{status_icon} Test Result: {'PASS' if result.success else 'FAIL'}")
        print(f"Test ID: {result.test_id}")
        print(f"Execution Time: {result.execution_time:.2f}s")
        
        if result.error_message:
            print(f"❌ Error: {result.error_message}")
            return
        
        # Constraint violations
        if result.constraint_violations:
            print(f"\n🚫 Constraint Violations ({len(result.constraint_violations)}):")
            for i, violation in enumerate(result.constraint_violations, 1):
                print(f"  {i}. {violation}")
        else:
            print("\n✅ No constraint violations")
        
        # Change verification
        verification = result.change_verification
        if verification.get("all_changes_applied"):
            print("✅ All intended changes applied")
        else:
            print("❌ Some intended changes not applied")
            
            if verification.get("missing_changes"):
                print("   Missing changes:")
                for change in verification["missing_changes"]:
                    print(f"     - {change}")
            
            if verification.get("unexpected_changes"):
                print("   Unexpected changes:")
                for change in verification["unexpected_changes"]:
                    print(f"     - {change}")
        
        # Unrelated changes
        if result.unrelated_changes:
            print(f"\n⚠️  Unrelated Changes ({len(result.unrelated_changes)}):")
            for i, change in enumerate(result.unrelated_changes, 1):
                print(f"  {i}. {change}")
        else:
            print("\n✅ No unrelated data altered")
        
        # Changes applied summary
        if result.changes_applied:
            print(f"\n📊 Changes Applied Summary:")
            table_data = []
            for table, ops in result.changes_applied.items():
                table_data.append([
                    table,
                    ops.get('insert', 0),
                    ops.get('update', 0),
                    ops.get('delete', 0)
                ])
            
            headers = ['Table', 'Inserts', 'Updates', 'Deletes']
            print(tabulate.tabulate(table_data, headers=headers, tablefmt='grid'))
    
    def _print_batch_summary(self, results: List[TestResult]):
        """Print batch test summary"""
        passed = sum(1 for r in results if r.success)
        failed = len(results) - passed
        
        print(f"\n📋 Batch Test Summary")
        print("=" * 40)
        print(f"Total Tests: {len(results)}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"Success Rate: {(passed/len(results)*100):.1f}%" if results else "0%")
        
        if failed > 0:
            print(f"\n❌ Failed Tests:")
            for i, result in enumerate(results, 1):
                if not result.success:
                    print(f"  {i}. {result.query[:50]}...")
                    if result.error_message:
                        print(f"      Error: {result.error_message}")
                    else:
                        issues = []
                        if result.constraint_violations:
                            issues.append(f"{len(result.constraint_violations)} constraint violations")
                        if not result.change_verification.get("all_changes_applied"):
                            issues.append("incomplete changes")
                        if result.unrelated_changes:
                            issues.append(f"{len(result.unrelated_changes)} unrelated changes")
                        print(f"      Issues: {', '.join(issues)}")
    
    def _print_help(self):
        """Print help information"""
        help_text = """
Available Commands:
  help          - Show this help
  quit/exit/q   - Exit interactive mode
  
Test Examples:
  Add option 'PhD' to education field
  Create new field 'phone_number' in contact form
  Update 'Bachelor' to 'Bachelor Degree' in education options
  Delete 'Other' option from experience field
  
The test framework will:
  ✅ Create a sandbox copy of your database
  ✅ Apply the generated changes
  ✅ Check for constraint violations
  ✅ Verify intended changes were applied exactly once
  ✅ Detect any unrelated data alterations
        """
        print(help_text)
    
    def generate_test_cases_template(self, output_file: str = "test_cases_template.json"):
        """Generate a template file for batch testing"""
        template = [
            {
                "description": "Add new option to dropdown field",
                "query": "Add option 'Graduate Degree' to education field",
                "expected_changes": {
                    "option_items": {
                        "insert": 1
                    }
                }
            },
            {
                "description": "Update existing option",
                "query": "Change 'Bachelor' to 'Bachelor Degree' in education field",
                "expected_changes": {
                    "option_items": {
                        "update": 1
                    }
                }
            },
            {
                "description": "Delete option",
                "query": "Remove 'Other' option from experience field",
                "expected_changes": {
                    "option_items": {
                        "delete": 1
                    }
                }
            },
            {
                "description": "Create new field",
                "query": "Add a 'phone_number' field to the contact form",
                "expected_changes": {
                    "form_fields": {
                        "insert": 1
                    }
                }
            },
            {
                "description": "Add conditional logic",
                "query": "Show 'experience_details' field when experience is 'Professional'",
                "expected_changes": {
                    "logic_rules": {
                        "insert": 1
                    },
                    "logic_conditions": {
                        "insert": 1
                    },
                    "logic_actions": {
                        "insert": 2
                    }
                }
            }
        ]
        
        with open(output_file, 'w') as f:
            json.dump(template, f, indent=2)
        
        print(f"📝 Generated test cases template: {output_file}")
        print("Edit this file to customize your test cases, then run:")
        print(f"python test_runner.py --batch {output_file}")


def main():
    """Main entry point for command-line usage"""
    parser = argparse.ArgumentParser(
        description="DB Simulation Test Runner for validating agent responses",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --query "Add option 'PhD' to education field"
  %(prog)s --batch test_cases.json
  %(prog)s --interactive
  %(prog)s --generate-template
        """
    )
    
    parser.add_argument(
        '--query', '-q',
        help='Single query to test'
    )
    
    parser.add_argument(
        '--batch', '-b',
        help='JSON file containing batch test cases'
    )
    
    parser.add_argument(
        '--interactive', '-i',
        action='store_true',
        help='Run in interactive mode'
    )
    
    parser.add_argument(
        '--generate-template', '-g',
        action='store_true',
        help='Generate test cases template file'
    )
    
    parser.add_argument(
        '--db-path',
        help='Path to database file (defaults to DATABASE_PATH env var or data/forms.sqlite)'
    )
    
    parser.add_argument(
        '--output-dir',
        default='test_results',
        help='Directory for test results (default: test_results)'
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if not any([args.query, args.batch, args.interactive, args.generate_template]):
        parser.error("Must specify one of: --query, --batch, --interactive, or --generate-template")
    
    try:
        runner = TestRunner(args.db_path, args.output_dir)
        
        if args.generate_template:
            runner.generate_test_cases_template()
        
        elif args.query:
            result = runner.run_single_test(args.query)
            sys.exit(0 if result.success else 1)
        
        elif args.batch:
            results = runner.run_batch_from_file(args.batch)
            success_count = sum(1 for r in results if r.success)
            sys.exit(0 if success_count == len(results) else 1)
        
        elif args.interactive:
            runner.run_interactive_mode()
    
    except KeyboardInterrupt:
        print("\n👋 Test run interrupted by user")
        sys.exit(1)
    
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()