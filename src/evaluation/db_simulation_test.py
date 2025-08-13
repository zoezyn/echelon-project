import sqlite3
import shutil
import tempfile
import os
import json
from typing import Dict, Any, List, Tuple, Optional
from pathlib import Path
import hashlib
from dataclasses import dataclass
from datetime import datetime

from ..utils.database import DatabaseManager
from ..utils.logger import setup_logger
from ..agent.workflow import FormAgentWorkflow


@dataclass
class TestResult:
    """Result of a DB simulation test"""
    test_id: str
    query: str
    success: bool
    constraint_violations: List[str]
    change_verification: Dict[str, Any]
    unrelated_changes: List[str]
    execution_time: float
    error_message: Optional[str] = None
    changes_applied: Optional[Dict[str, Any]] = None


class DBSimulationTest:
    """
    DB Simulation Test framework for validating agent responses.
    
    This class creates a sandbox copy of the SQLite database, applies
    generated changes, and validates correctness through:
    - Constraint violation checks
    - Intended change verification
    - Unrelated data alteration detection
    """
    
    def __init__(self, db_path: str = None, test_output_dir: str = "test_results"):
        self.logger = setup_logger("DBSimulationTest")
        self.original_db_path = db_path or os.getenv('DATABASE_PATH', 'data/forms.sqlite')
        self.test_output_dir = Path(test_output_dir)
        self.test_output_dir.mkdir(exist_ok=True)
        
        # Initialize workflow for testing
        self.workflow = FormAgentWorkflow()
        
        # Store original database state for comparison
        self.original_db_hash = self._calculate_db_hash(self.original_db_path)
        
        self.logger.info(f"Initialized DB Simulation Test with database: {self.original_db_path}")
    
    def run_test(self, query: str, expected_changes: Dict[str, Any] = None) -> TestResult:
        """
        Run a complete DB simulation test for a given query.
        
        Args:
            query: User query to test
            expected_changes: Optional dict of expected changes for validation
            
        Returns:
            TestResult with validation results
        """
        test_id = self._generate_test_id(query)
        start_time = datetime.now()
        
        self.logger.info(f"Starting DB simulation test {test_id} for query: {query}")
        
        try:
            # Step 1: Create sandbox database
            sandbox_db_path = self._create_sandbox_db(test_id)
            
            # Step 2: Capture initial state
            initial_state = self._capture_database_state(sandbox_db_path)
            
            # Step 3: Generate changes using agent
            agent_response = self.workflow.process_query(query)
            
            if not agent_response or "error" in agent_response:
                error_msg = agent_response.get("error", "Agent failed to generate response")
                execution_time = (datetime.now() - start_time).total_seconds()
                return TestResult(
                    test_id=test_id,
                    query=query,
                    success=False,
                    constraint_violations=[],
                    change_verification={},
                    unrelated_changes=[],
                    execution_time=execution_time,
                    error_message=error_msg
                )
            
            # Step 4: Apply changes to sandbox
            changes_applied = self._apply_changes_to_sandbox(sandbox_db_path, agent_response)
            
            # Step 5: Capture final state
            final_state = self._capture_database_state(sandbox_db_path)
            
            # Step 6: Validate results
            constraint_violations = self._check_constraint_violations(sandbox_db_path)
            change_verification = self._verify_intended_changes(
                initial_state, final_state, agent_response, expected_changes
            )
            unrelated_changes = self._detect_unrelated_changes(
                initial_state, final_state, agent_response
            )
            
            execution_time = (datetime.now() - start_time).total_seconds()
            success = (
                len(constraint_violations) == 0 and
                change_verification.get("all_changes_applied", False) and
                len(unrelated_changes) == 0
            )
            
            result = TestResult(
                test_id=test_id,
                query=query,
                success=success,
                constraint_violations=constraint_violations,
                change_verification=change_verification,
                unrelated_changes=unrelated_changes,
                execution_time=execution_time,
                changes_applied=changes_applied
            )
            
            # Step 7: Save test results
            self._save_test_result(result, initial_state, final_state)
            
            # # Step 8: Cleanup sandbox
            # self._cleanup_sandbox(sandbox_db_path)
            
            self.logger.info(f"Test {test_id} completed. Success: {success}")
            return result
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            self.logger.error(f"Test {test_id} failed with error: {str(e)}")
            
            return TestResult(
                test_id=test_id,
                query=query,
                success=False,
                constraint_violations=[],
                change_verification={},
                unrelated_changes=[],
                execution_time=execution_time,
                error_message=str(e)
            )
    
    def _generate_test_id(self, query: str) -> str:
        """Generate unique test ID based on query and timestamp"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        query_hash = hashlib.md5(query.encode()).hexdigest()[:8]
        return f"test_{timestamp}_{query_hash}"
    
    def _create_sandbox_db(self, test_id: str) -> str:
        """Create a copy of the database for sandbox testing"""
        sandbox_path = self.test_output_dir / f"{test_id}_sandbox.sqlite"
        
        if not os.path.exists(self.original_db_path):
            raise FileNotFoundError(f"Original database not found: {self.original_db_path}")
        
        shutil.copy2(self.original_db_path, sandbox_path)
        
        # Verify copy integrity
        if self._calculate_db_hash(sandbox_path) != self.original_db_hash:
            raise RuntimeError("Sandbox database copy failed integrity check")
        
        self.logger.debug(f"Created sandbox database: {sandbox_path}")
        return str(sandbox_path)
    
    def _capture_database_state(self, db_path: str) -> Dict[str, Any]:
        """Capture complete state of database for comparison"""
        state = {
            "tables": {},
            "table_counts": {},
            "schema": {},
            "indexes": {},
            "triggers": {},
            "checksum": self._calculate_db_hash(db_path)
        }
        
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get all table names
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            for table in tables:
                # Get table data
                cursor.execute(f"SELECT * FROM {table}")
                rows = [dict(row) for row in cursor.fetchall()]
                state["tables"][table] = rows
                state["table_counts"][table] = len(rows)
                
                # Get table schema
                cursor.execute(f"PRAGMA table_info({table})")
                columns = [dict(row) for row in cursor.fetchall()]
                state["schema"][table] = columns
                
                # Get indexes for this table
                cursor.execute(f"PRAGMA index_list({table})")
                indexes = [dict(row) for row in cursor.fetchall()]
                state["indexes"][table] = indexes
            
            # Get triggers
            cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='trigger'")
            triggers = [dict(row) for row in cursor.fetchall()]
            state["triggers"] = triggers
        
        return state
    
    def _apply_changes_to_sandbox(self, sandbox_db_path: str, agent_response: Dict[str, Any]) -> Dict[str, Any]:
        """Apply agent-generated changes to sandbox database"""
        changes_applied = {}
        
        try:
            with sqlite3.connect(sandbox_db_path) as conn:
                cursor = conn.cursor()
                
                # Enable foreign key constraints
                cursor.execute("PRAGMA foreign_keys = ON")
                
                # Process each table's changes
                for table_name, operations in agent_response.items():
                    if not isinstance(operations, dict):
                        continue
                    
                    changes_applied[table_name] = {"insert": 0, "update": 0, "delete": 0}
                    
                    # Handle inserts
                    if "insert" in operations:
                        for record in operations["insert"]:
                            columns = list(record.keys())
                            placeholders = ["?" for _ in columns]
                            values = [record[col] for col in columns]
                            
                            query = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
                            cursor.execute(query, values)
                            changes_applied[table_name]["insert"] += 1
                    
                    # Handle updates
                    if "update" in operations:
                        for record in operations["update"]:
                            if "id" not in record:
                                self.logger.warning(f"Update record missing ID: {record}")
                                continue
                            
                            set_clauses = []
                            values = []
                            for key, value in record.items():
                                if key != "id":
                                    set_clauses.append(f"{key} = ?")
                                    values.append(value)
                            
                            if set_clauses:
                                values.append(record["id"])
                                query = f"UPDATE {table_name} SET {', '.join(set_clauses)} WHERE id = ?"
                                cursor.execute(query, values)
                                changes_applied[table_name]["update"] += cursor.rowcount
                    
                    # Handle deletes
                    if "delete" in operations:
                        for record in operations["delete"]:
                            if "id" not in record:
                                self.logger.warning(f"Delete record missing ID: {record}")
                                continue
                            
                            cursor.execute(f"DELETE FROM {table_name} WHERE id = ?", (record["id"],))
                            changes_applied[table_name]["delete"] += cursor.rowcount
                
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"Error applying changes to sandbox: {str(e)}")
            raise
        
        return changes_applied
    
    def _check_constraint_violations(self, db_path: str) -> List[str]:
        """Check for database constraint violations"""
        violations = []
        
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                
                # Check foreign key constraints
                cursor.execute("PRAGMA foreign_key_check")
                fk_violations = cursor.fetchall()
                for violation in fk_violations:
                    violations.append(f"Foreign key violation in table {violation[0]}: {violation[3]}")
                
                # Check integrity
                cursor.execute("PRAGMA integrity_check")
                integrity_results = cursor.fetchall()
                for result in integrity_results:
                    if result[0] != "ok":
                        violations.append(f"Integrity check failed: {result[0]}")
                
                # Check unique constraints by attempting to find duplicates
                # Get all tables
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                for table in tables:
                    # Get unique constraints from schema
                    cursor.execute(f"PRAGMA index_list({table})")
                    indexes = cursor.fetchall()
                    
                    for index in indexes:
                        if index[2]:  # is unique
                            cursor.execute(f"PRAGMA index_info({index[1]})")
                            index_columns = [col[2] for col in cursor.fetchall()]
                            
                            # Check for duplicates
                            columns_str = ", ".join(index_columns)
                            cursor.execute(f"""
                                SELECT {columns_str}, COUNT(*) 
                                FROM {table} 
                                GROUP BY {columns_str} 
                                HAVING COUNT(*) > 1
                            """)
                            duplicates = cursor.fetchall()
                            
                            for dup in duplicates:
                                violations.append(f"Unique constraint violation in {table}.{columns_str}: duplicate values {dup[:-1]}")
                
        except Exception as e:
            violations.append(f"Error checking constraints: {str(e)}")
        
        return violations
    
    def _verify_intended_changes(
        self, 
        initial_state: Dict[str, Any], 
        final_state: Dict[str, Any], 
        agent_response: Dict[str, Any],
        expected_changes: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Verify that intended changes were applied exactly once"""
        verification = {
            "all_changes_applied": True,
            "changes_applied_once": True,
            "expected_vs_actual": {},
            "missing_changes": [],
            "unexpected_changes": [],
            "duplicate_changes": []
        }
        
        # Compare table counts to detect changes
        for table in initial_state["table_counts"]:
            initial_count = initial_state["table_counts"][table]
            final_count = final_state["table_counts"].get(table, 0)
            
            expected_inserts = len(agent_response.get(table, {}).get("insert", []))
            expected_deletes = len(agent_response.get(table, {}).get("delete", []))
            expected_final_count = initial_count + expected_inserts - expected_deletes
            
            if final_count != expected_final_count:
                verification["all_changes_applied"] = False
                verification["unexpected_changes"].append({
                    "table": table,
                    "expected_count": expected_final_count,
                    "actual_count": final_count,
                    "initial_count": initial_count
                })
        
        # Verify specific record changes
        for table_name, operations in agent_response.items():
            if not isinstance(operations, dict):
                continue
            
            # Check inserts
            if "insert" in operations:
                for record in operations["insert"]:
                    # Find this record in final state
                    found = self._find_record_in_state(final_state, table_name, record)
                    if not found:
                        verification["all_changes_applied"] = False
                        verification["missing_changes"].append({
                            "operation": "insert",
                            "table": table_name,
                            "record": record
                        })
            
            # Check updates
            if "update" in operations:
                for record in operations["update"]:
                    if "id" in record:
                        # Verify the record exists with updated values
                        found = self._find_record_by_id(final_state, table_name, record["id"])
                        if found:
                            # Check if update was applied
                            for key, expected_value in record.items():
                                if key != "id" and found.get(key) != expected_value:
                                    verification["all_changes_applied"] = False
                                    verification["missing_changes"].append({
                                        "operation": "update",
                                        "table": table_name,
                                        "record_id": record["id"],
                                        "field": key,
                                        "expected": expected_value,
                                        "actual": found.get(key)
                                    })
                        else:
                            verification["all_changes_applied"] = False
                            verification["missing_changes"].append({
                                "operation": "update",
                                "table": table_name,
                                "record_id": record["id"],
                                "error": "Record not found after update"
                            })
            
            # Check deletes
            if "delete" in operations:
                for record in operations["delete"]:
                    if "id" in record:
                        found = self._find_record_by_id(final_state, table_name, record["id"])
                        if found:
                            verification["all_changes_applied"] = False
                            verification["missing_changes"].append({
                                "operation": "delete",
                                "table": table_name,
                                "record_id": record["id"],
                                "error": "Record still exists after delete"
                            })
        
        return verification
    
    def _detect_unrelated_changes(
        self, 
        initial_state: Dict[str, Any], 
        final_state: Dict[str, Any], 
        agent_response: Dict[str, Any]
    ) -> List[str]:
        """Detect any changes to data that wasn't part of the intended changes"""
        unrelated_changes = []
        
        for table_name in initial_state["tables"]:
            initial_records = {self._get_record_key(r): r for r in initial_state["tables"][table_name]}
            final_records = {self._get_record_key(r): r for r in final_state["tables"].get(table_name, [])}
            
            # Get IDs that should have been modified according to agent response
            expected_modified_ids = set()
            operations = agent_response.get(table_name, {})
            
            # Collect IDs from updates and deletes
            for record in operations.get("update", []):
                if "id" in record:
                    expected_modified_ids.add(record["id"])
            
            for record in operations.get("delete", []):
                if "id" in record:
                    expected_modified_ids.add(record["id"])
            
            # Check for unrelated modifications
            for key, initial_record in initial_records.items():
                final_record = final_records.get(key)
                record_id = initial_record.get("id")
                
                # Skip if this record was supposed to be modified
                if record_id in expected_modified_ids:
                    continue
                
                # Skip if record was deleted as intended
                if not final_record and record_id in [r.get("id") for r in operations.get("delete", [])]:
                    continue
                
                if not final_record:
                    unrelated_changes.append(f"Unrelated deletion in {table_name}: record {record_id}")
                elif initial_record != final_record:
                    # Find which fields changed
                    changed_fields = []
                    for field, initial_value in initial_record.items():
                        if final_record.get(field) != initial_value:
                            changed_fields.append(f"{field}: {initial_value} -> {final_record.get(field)}")
                    
                    if changed_fields:
                        unrelated_changes.append(
                            f"Unrelated modification in {table_name}, record {record_id}: {', '.join(changed_fields)}"
                        )
            
            # Check for unrelated additions
            for key, final_record in final_records.items():
                if key not in initial_records:
                    record_id = final_record.get("id")
                    # Check if this was an intended insert
                    is_intended_insert = False
                    for insert_record in operations.get("insert", []):
                        if self._records_match(insert_record, final_record):
                            is_intended_insert = True
                            break
                    
                    if not is_intended_insert:
                        unrelated_changes.append(f"Unrelated addition in {table_name}: record {record_id}")
        
        return unrelated_changes
    
    def _find_record_in_state(self, state: Dict[str, Any], table_name: str, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Find a record in the database state"""
        if table_name not in state["tables"]:
            return None
        
        for existing_record in state["tables"][table_name]:
            if self._records_match(record, existing_record):
                return existing_record
        
        return None
    
    def _find_record_by_id(self, state: Dict[str, Any], table_name: str, record_id: str) -> Optional[Dict[str, Any]]:
        """Find a record by ID in the database state"""
        if table_name not in state["tables"]:
            return None
        
        for record in state["tables"][table_name]:
            if record.get("id") == record_id:
                return record
        
        return None
    
    def _records_match(self, record1: Dict[str, Any], record2: Dict[str, Any]) -> bool:
        """Check if two records match (ignoring placeholder IDs)"""
        for key, value in record1.items():
            # Skip placeholder IDs that start with $
            if key == "id" and (str(value).startswith("$") or str(record2.get(key, "")).startswith("$")):
                continue
            
            if record2.get(key) != value:
                return False
        
        return True
    
    def _get_record_key(self, record: Dict[str, Any]) -> str:
        """Generate a key for a record for comparison purposes"""
        record_id = record.get("id", "")
        if record_id:
            return str(record_id)
        
        # For records without ID, use all fields
        sorted_items = sorted(record.items())
        return str(hash(tuple(sorted_items)))
    
    def _calculate_db_hash(self, db_path: str) -> str:
        """Calculate hash of database file for integrity checking"""
        hash_md5 = hashlib.md5()
        with open(db_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def _save_test_result(
        self, 
        result: TestResult, 
        initial_state: Dict[str, Any], 
        final_state: Dict[str, Any]
    ):
        """Save test result to file"""
        result_data = {
            "test_result": {
                "test_id": result.test_id,
                "query": result.query,
                "success": result.success,
                "constraint_violations": result.constraint_violations,
                "change_verification": result.change_verification,
                "unrelated_changes": result.unrelated_changes,
                "execution_time": result.execution_time,
                "error_message": result.error_message,
                "changes_applied": result.changes_applied,
                "timestamp": datetime.now().isoformat()
            },
            "database_states": {
                "initial": {
                    "table_counts": initial_state["table_counts"],
                    "checksum": initial_state["checksum"]
                },
                "final": {
                    "table_counts": final_state["table_counts"],
                    "checksum": final_state["checksum"]
                }
            }
        }
        
        result_file = self.test_output_dir / f"{result.test_id}_result.json"
        with open(result_file, 'w') as f:
            json.dump(result_data, f, indent=2, default=str)
        
        self.logger.debug(f"Saved test result: {result_file}")
    
    def _cleanup_sandbox(self, sandbox_db_path: str):
        """Clean up sandbox database file"""
        try:
            os.unlink(sandbox_db_path)
            self.logger.debug(f"Cleaned up sandbox: {sandbox_db_path}")
        except Exception as e:
            self.logger.warning(f"Failed to cleanup sandbox {sandbox_db_path}: {e}")
    
    def run_batch_tests(self, test_cases: List[Dict[str, Any]]) -> List[TestResult]:
        """Run multiple tests in batch"""
        results = []
        
        self.logger.info(f"Starting batch test run with {len(test_cases)} test cases")
        
        for i, test_case in enumerate(test_cases, 1):
            self.logger.info(f"Running test {i}/{len(test_cases)}")
            
            query = test_case.get("query")
            expected_changes = test_case.get("expected_changes")
            
            if not query:
                self.logger.warning(f"Test case {i} missing query, skipping")
                continue
            
            result = self.run_test(query, expected_changes)
            results.append(result)
            
            # Log summary
            status = "✅ PASS" if result.success else "❌ FAIL"
            self.logger.info(f"Test {i}: {status} - {query[:50]}...")
        
        # Generate batch summary
        passed = sum(1 for r in results if r.success)
        failed = len(results) - passed
        
        self.logger.info(f"Batch test completed: {passed} passed, {failed} failed")
        
        return results