"""
Validator Agent - LLM-Based Changeset Validation

This agent specializes in validating database changesets by applying them to
an in-memory copy of the SQLite database and providing structured validation
results with error details and suggestions.
"""

import sqlite3
import json
import tempfile
import shutil
import uuid
from typing import Dict, List, Optional, Any
from agents import Agent, function_tool
from ..utils.logger import get_agent_logger, log_json_pretty


class ValidatorAgent:
    """
    LLM-powered agent that validates database changesets
    
    This agent applies changes to in-memory database copies, validates
    constraints and relationships, and provides structured validation
    results with detailed error reporting and suggestions for fixes.
    """
    
    def __init__(self, model="gpt-4", db_path="data/forms.sqlite"):
        self.db_path = db_path
        self.temp_db_path = None
        self.model = model
        
        # Initialize logging
        self.logger = get_agent_logger("ValidatorAgent", "DEBUG")
        self.logger.log_step("Initializing ValidatorAgent", {
            "model": model,
            "db_path": db_path
        })
        
        # Create function tools
        self.tools = self._create_tools()
        self.logger.log_step(f"Created {len(self.tools)} validation tools")
        
        self.agent = Agent(
            name="ValidatorAgent",
            model=model,
            instructions=self._get_instructions(),
            tools=self.tools
        )
        
        self.logger.log_step("ValidatorAgent initialized successfully")
        
    def _get_instructions(self):
        return """# Validator Agent

You are a specialized LLM agent for validating database changesets for enterprise form systems. Your job is to ensure that proposed changes are safe, valid, and maintain data integrity.

## Your Expertise

You understand database validation including:
- Foreign key constraint validation
- Required field validation
- Data type validation
- Unique constraint validation
- Business logic validation
- Referential integrity checks

## Available Tools

- **create_temp_database**: Create temporary copy of database for testing
- **apply_changeset**: Apply a changeset to the temporary database
- **validate_foreign_keys**: Check all foreign key constraints
- **validate_required_fields**: Check required fields are present
- **validate_data_types**: Check data types match schema
- **validate_unique_constraints**: Check unique constraints
- **generate_diff**: Generate diff showing what would change
- **check_referential_integrity**: Check referential integrity
- **get_validation_summary**: Get high-level validation summary
- **cleanup_temp_database**: Clean up temporary database

## Core Responsibilities

1. **Validate safely**: Apply changes to temporary database copy
2. **Check constraints**: Validate all database constraints and relationships
3. **Provide feedback**: Give detailed error messages and suggestions
4. **Generate diffs**: Show exactly what would change
5. **Ensure integrity**: Maintain data consistency and referential integrity

## Validation Process

1. Create temporary database copy
2. Apply changeset to temporary database
3. Run comprehensive validation checks
4. Generate structured results with errors/warnings
5. Provide suggestions for fixing issues
6. Clean up temporary resources

## Guidelines

- Always validate in isolation using temporary database copies
- Provide clear, actionable error messages
- Suggest specific fixes for validation failures
- Check both structural and data integrity
- Return comprehensive validation results
- Clean up resources after validation

When validation fails, provide specific suggestions for how to fix the issues."""

    def _create_tools(self) -> List:
        """Create function tools using @function_tool decorator"""
        
        @function_tool
        def validate_changeset_tool(changeset: str) -> str:
            """Validate a database changeset by applying it to an in-memory copy
            
            Args:
                changeset: JSON string of the changeset to validate
            """
            try:
                changeset_dict = json.loads(changeset)
                result = self.validate_changeset(changeset_dict)
                return json.dumps(result, indent=2)
            except Exception as e:
                return f"Error validating changeset: {str(e)}"
        
        @function_tool
        def create_temp_database_tool() -> str:
            """Create a temporary copy of the database for testing"""
            try:
                result = self.create_temp_database()
                return json.dumps(result, indent=2)
            except Exception as e:
                return f"Error creating temp database: {str(e)}"
        
        @function_tool
        def apply_changeset_tool(changeset: str) -> str:
            """Apply a changeset to the temporary database
            
            Args:
                changeset: JSON string of the changeset to apply
            """
            try:
                changeset_dict = json.loads(changeset)
                result = self.apply_changeset(changeset_dict)
                return json.dumps(result, indent=2)
            except Exception as e:
                return f"Error applying changeset: {str(e)}"
        
        @function_tool
        def validate_foreign_keys_tool() -> str:
            """Check all foreign key constraints in the temporary database"""
            try:
                result = self.validate_foreign_keys()
                return json.dumps(result, indent=2)
            except Exception as e:
                return f"Error validating foreign keys: {str(e)}"
        
        @function_tool
        def validate_required_fields_tool(changeset: str) -> str:
            """Check that required fields are present in all operations
            
            Args:
                changeset: JSON string of the changeset to check
            """
            try:
                changeset_dict = json.loads(changeset)
                result = self.validate_required_fields(changeset_dict)
                return json.dumps(result, indent=2)
            except Exception as e:
                return f"Error validating required fields: {str(e)}"
        
        @function_tool
        def validate_data_types_tool(changeset: str) -> str:
            """Check that data types match the schema
            
            Args:
                changeset: JSON string of the changeset to check
            """
            try:
                changeset_dict = json.loads(changeset)
                result = self.validate_data_types(changeset_dict)
                return json.dumps(result, indent=2)
            except Exception as e:
                return f"Error validating data types: {str(e)}"
        
        @function_tool
        def generate_diff_tool(changeset: str) -> str:
            """Generate a diff showing what would change
            
            Args:
                changeset: JSON string of the changeset to diff
            """
            try:
                changeset_dict = json.loads(changeset)
                result = self.generate_diff(changeset_dict)
                return json.dumps(result, indent=2)
            except Exception as e:
                return f"Error generating diff: {str(e)}"
        
        @function_tool
        def check_referential_integrity_tool() -> str:
            """Check referential integrity after changes"""
            try:
                result = self.check_referential_integrity()
                return json.dumps(result, indent=2)
            except Exception as e:
                return f"Error checking referential integrity: {str(e)}"
        
        @function_tool
        def cleanup_temp_database_tool() -> str:
            """Clean up temporary database resources"""
            try:
                result = self.cleanup_temp_database()
                return json.dumps(result, indent=2)
            except Exception as e:
                return f"Error cleaning up: {str(e)}"
        
        return [
            validate_changeset_tool, create_temp_database_tool, apply_changeset_tool,
            validate_foreign_keys_tool, validate_required_fields_tool, validate_data_types_tool,
            generate_diff_tool, check_referential_integrity_tool, cleanup_temp_database_tool
        ]

    def create_temp_database(self) -> Dict:
        """Create a temporary copy of the database for testing"""
        self.logger.log_step("Creating temporary database for validation")
        
        try:
            # Create temporary file
            self.logger.log_thinking("Creating temporary file...")
            temp_fd, self.temp_db_path = tempfile.mkstemp(suffix='.sqlite')
            import os
            os.close(temp_fd)
            
            self.logger.log_step("Temporary file created", {
                "temp_path": self.temp_db_path
            })
            
            # Copy original database to temporary location
            self.logger.log_thinking(f"Copying database from {self.db_path} to temporary location...")
            shutil.copy2(self.db_path, self.temp_db_path)
            
            # Get file sizes for verification
            original_size = os.path.getsize(self.db_path)
            temp_size = os.path.getsize(self.temp_db_path)
            
            result = {
                "success": True,
                "temp_path": self.temp_db_path,
                "message": "Temporary database created successfully"
            }
            
            self.logger.log_step("Database copied successfully", {
                "original_size": original_size,
                "temp_size": temp_size,
                "size_match": original_size == temp_size
            })
            
            return result
            
        except Exception as e:
            self.logger.log_error(e, "create_temp_database")
            return {"success": False, "error": f"Failed to create temp database: {str(e)}"}

    def apply_changeset(self, changeset: Dict) -> Dict:
        """Apply a changeset to the temporary database"""
        self.logger.log_step("Starting changeset application", {
            "table_count": len(changeset),
            "tables": list(changeset.keys())
        })
        
        if not self.temp_db_path:
            self.logger.log_thinking("No temporary database exists, creating one...")
            result = self.create_temp_database()
            if not result["success"]:
                return result
        
        log_json_pretty(self.logger, "CHANGESET TO APPLY", changeset, "DEBUG")
        
        try:
            with sqlite3.connect(self.temp_db_path) as conn:
                cursor = conn.cursor()
                applied_operations = []
                errors = []
                
                self.logger.log_step("Connected to temporary database, processing operations...")
                
                # Process each table in the changeset
                for table_name, operations in changeset.items():
                    self.logger.log_step(f"Processing table: {table_name}", {
                        "inserts": len(operations.get("insert", [])),
                        "updates": len(operations.get("update", [])),
                        "deletes": len(operations.get("delete", []))
                    })
                    
                    # Process INSERT operations
                    for i, record in enumerate(operations.get("insert", [])):
                        try:
                            self.logger.log_thinking(f"Processing INSERT {i+1} for {table_name}")
                            columns = list(record.keys())
                            values = list(record.values())
                            placeholders = ','.join(['?' for _ in values])
                            
                            query = f"INSERT INTO {table_name} ({','.join(columns)}) VALUES ({placeholders})"
                            self.logger.log_step(f"Executing INSERT query", {
                                "table": table_name,
                                "columns": columns,
                                "query": query
                            }, "DEBUG")
                            
                            cursor.execute(query, values)
                            applied_operations.append({
                                "operation": "insert",
                                "table": table_name,
                                "record": record
                            })
                            self.logger.log_step(f"INSERT successful for {table_name}")
                            
                        except Exception as e:
                            error_detail = {
                                "operation": "insert",
                                "table": table_name,
                                "record": record,
                                "error": str(e)
                            }
                            errors.append(error_detail)
                            self.logger.log_error(e, f"INSERT failed for {table_name}")
                            log_json_pretty(self.logger, "INSERT ERROR DETAILS", error_detail, "ERROR")
                    
                    # Process UPDATE operations
                    for record in operations.get("update", []):
                        try:
                            record_id = record.pop("id") if "id" in record else None
                            if not record_id:
                                errors.append({
                                    "operation": "update",
                                    "table": table_name,
                                    "record": record,
                                    "error": "Update operation missing 'id' field"
                                })
                                continue
                            
                            set_clauses = [f"{col} = ?" for col in record.keys()]
                            values = list(record.values()) + [record_id]
                            
                            query = f"UPDATE {table_name} SET {','.join(set_clauses)} WHERE id = ?"
                            cursor.execute(query, values)
                            applied_operations.append({
                                "operation": "update",
                                "table": table_name,
                                "id": record_id,
                                "changes": record
                            })
                        except Exception as e:
                            errors.append({
                                "operation": "update",
                                "table": table_name,
                                "record": record,
                                "error": str(e)
                            })
                    
                    # Process DELETE operations
                    for record in operations.get("delete", []):
                        try:
                            record_id = record.get("id")
                            if not record_id:
                                errors.append({
                                    "operation": "delete",
                                    "table": table_name,
                                    "record": record,
                                    "error": "Delete operation missing 'id' field"
                                })
                                continue
                            
                            query = f"DELETE FROM {table_name} WHERE id = ?"
                            cursor.execute(query, (record_id,))
                            applied_operations.append({
                                "operation": "delete",
                                "table": table_name,
                                "id": record_id
                            })
                        except Exception as e:
                            errors.append({
                                "operation": "delete",
                                "table": table_name,
                                "record": record,
                                "error": str(e)
                            })
                
                conn.commit()
                
                return {
                    "success": len(errors) == 0,
                    "applied_operations": applied_operations,
                    "errors": errors,
                    "message": f"Applied {len(applied_operations)} operations with {len(errors)} errors"
                }
                
        except Exception as e:
            return {"success": False, "error": f"Failed to apply changeset: {str(e)}"}

    def validate_foreign_keys(self) -> Dict:
        """Check all foreign key constraints"""
        if not self.temp_db_path:
            return {"success": False, "error": "No temporary database available"}
        
        try:
            with sqlite3.connect(self.temp_db_path) as conn:
                cursor = conn.cursor()
                
                # Enable foreign key constraint checking
                cursor.execute("PRAGMA foreign_keys = ON")
                
                # Check foreign key constraints
                cursor.execute("PRAGMA foreign_key_check")
                fk_violations = cursor.fetchall()
                
                violations = []
                for violation in fk_violations:
                    violations.append({
                        "table": violation[0],
                        "row_id": violation[1],
                        "parent_table": violation[2],
                        "constraint_index": violation[3]
                    })
                
                return {
                    "valid": len(violations) == 0,
                    "violations": violations,
                    "message": f"Found {len(violations)} foreign key violations"
                }
                
        except Exception as e:
            return {"valid": False, "error": f"Failed to validate foreign keys: {str(e)}"}

    def validate_required_fields(self, changeset: Dict) -> Dict:
        """Check that required fields are present"""
        try:
            errors = []
            
            # Get schema info for required field checking
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                for table_name, operations in changeset.items():
                    # Get table schema
                    cursor.execute(f"PRAGMA table_info({table_name})")
                    schema = cursor.fetchall()
                    required_fields = [col[1] for col in schema if col[3] == 1]  # not_null = 1
                    
                    # Check INSERT operations
                    for record in operations.get("insert", []):
                        missing_required = [field for field in required_fields if field not in record or record[field] is None]
                        if missing_required:
                            errors.append({
                                "operation": "insert",
                                "table": table_name,
                                "missing_fields": missing_required,
                                "record": record
                            })
                    
                    # UPDATE operations don't need to include all required fields
                    # Just check that we're not setting required fields to null
                    for record in operations.get("update", []):
                        null_required = [field for field in required_fields if field in record and record[field] is None]
                        if null_required:
                            errors.append({
                                "operation": "update",
                                "table": table_name,
                                "null_required_fields": null_required,
                                "record": record
                            })
            
            return {
                "valid": len(errors) == 0,
                "errors": errors,
                "message": f"Found {len(errors)} required field violations"
            }
            
        except Exception as e:
            return {"valid": False, "error": f"Failed to validate required fields: {str(e)}"}

    def validate_data_types(self, changeset: Dict) -> Dict:
        """Check that data types match schema"""
        try:
            errors = []
            
            # Simple data type validation
            for table_name, operations in changeset.items():
                for operation_type in ["insert", "update"]:
                    for record in operations.get(operation_type, []):
                        for field_name, value in record.items():
                            if field_name == "id" and isinstance(value, str) and value.startswith("$"):
                                # Skip placeholder IDs
                                continue
                            
                            # Basic type checks
                            if field_name.endswith("_id") and value is not None:
                                if not isinstance(value, str):
                                    errors.append({
                                        "operation": operation_type,
                                        "table": table_name,
                                        "field": field_name,
                                        "expected_type": "string (ID)",
                                        "actual_value": value,
                                        "actual_type": type(value).__name__
                                    })
                            elif field_name in ["position", "priority", "required", "read_only", "visible_by_default", "enabled", "has_options", "allows_multiple"]:
                                if value is not None and not isinstance(value, (int, bool)):
                                    errors.append({
                                        "operation": operation_type,
                                        "table": table_name,
                                        "field": field_name,
                                        "expected_type": "integer/boolean",
                                        "actual_value": value,
                                        "actual_type": type(value).__name__
                                    })
            
            return {
                "valid": len(errors) == 0,
                "errors": errors,
                "message": f"Found {len(errors)} data type violations"
            }
            
        except Exception as e:
            return {"valid": False, "error": f"Failed to validate data types: {str(e)}"}

    def validate_unique_constraints(self) -> Dict:
        """Check unique constraints"""
        if not self.temp_db_path:
            return {"success": False, "error": "No temporary database available"}
        
        try:
            with sqlite3.connect(self.temp_db_path) as conn:
                cursor = conn.cursor()
                violations = []
                
                # Check known unique constraints
                unique_constraints = [
                    ("categories", "slug"),
                    ("forms", "slug"),
                    ("field_types", "key")
                ]
                
                for table, column in unique_constraints:
                    cursor.execute(f"""
                        SELECT {column}, COUNT(*) as count 
                        FROM {table} 
                        GROUP BY {column} 
                        HAVING COUNT(*) > 1
                    """)
                    duplicates = cursor.fetchall()
                    
                    for dup in duplicates:
                        violations.append({
                            "table": table,
                            "column": column,
                            "value": dup[0],
                            "count": dup[1]
                        })
                
                return {
                    "valid": len(violations) == 0,
                    "violations": violations,
                    "message": f"Found {len(violations)} unique constraint violations"
                }
                
        except Exception as e:
            return {"valid": False, "error": f"Failed to validate unique constraints: {str(e)}"}

    def generate_diff(self, changeset: Dict) -> Dict:
        """Generate a diff showing what would change"""
        try:
            diff = {
                "summary": {},
                "details": []
            }
            
            total_operations = 0
            
            for table_name, operations in changeset.items():
                table_ops = {
                    "inserts": len(operations.get("insert", [])),
                    "updates": len(operations.get("update", [])),
                    "deletes": len(operations.get("delete", []))
                }
                diff["summary"][table_name] = table_ops
                total_operations += sum(table_ops.values())
                
                # Add detailed changes
                for insert_record in operations.get("insert", []):
                    diff["details"].append({
                        "operation": "INSERT",
                        "table": table_name,
                        "data": insert_record
                    })
                
                for update_record in operations.get("update", []):
                    diff["details"].append({
                        "operation": "UPDATE", 
                        "table": table_name,
                        "id": update_record.get("id"),
                        "changes": {k: v for k, v in update_record.items() if k != "id"}
                    })
                
                for delete_record in operations.get("delete", []):
                    diff["details"].append({
                        "operation": "DELETE",
                        "table": table_name,
                        "id": delete_record.get("id")
                    })
            
            diff["total_operations"] = total_operations
            
            return {"success": True, "diff": diff}
            
        except Exception as e:
            return {"success": False, "error": f"Failed to generate diff: {str(e)}"}

    def check_referential_integrity(self) -> Dict:
        """Check referential integrity after changes"""
        if not self.temp_db_path:
            return {"success": False, "error": "No temporary database available"}
        
        try:
            with sqlite3.connect(self.temp_db_path) as conn:
                cursor = conn.cursor()
                integrity_issues = []
                
                # Check for orphaned records
                orphan_checks = [
                    ("form_pages", "form_id", "forms", "id"),
                    ("form_fields", "form_id", "forms", "id"),
                    ("form_fields", "page_id", "form_pages", "id"),
                    ("option_sets", "form_id", "forms", "id"),
                    ("option_items", "option_set_id", "option_sets", "id"),
                    ("logic_rules", "form_id", "forms", "id")
                ]
                
                for child_table, child_col, parent_table, parent_col in orphan_checks:
                    cursor.execute(f"""
                        SELECT {child_table}.{child_col}, COUNT(*) as count
                        FROM {child_table} 
                        LEFT JOIN {parent_table} ON {child_table}.{child_col} = {parent_table}.{parent_col}
                        WHERE {parent_table}.{parent_col} IS NULL AND {child_table}.{child_col} IS NOT NULL
                        GROUP BY {child_table}.{child_col}
                    """)
                    orphans = cursor.fetchall()
                    
                    for orphan in orphans:
                        integrity_issues.append({
                            "type": "orphaned_record",
                            "child_table": child_table,
                            "child_column": child_col,
                            "parent_table": parent_table,
                            "orphaned_value": orphan[0],
                            "count": orphan[1]
                        })
                
                return {
                    "valid": len(integrity_issues) == 0,
                    "issues": integrity_issues,
                    "message": f"Found {len(integrity_issues)} referential integrity issues"
                }
                
        except Exception as e:
            return {"valid": False, "error": f"Failed to check referential integrity: {str(e)}"}

    def get_validation_summary(self) -> Dict:
        """Get a high-level summary of validation results"""
        # This would aggregate results from previous validation steps
        # For now, return a placeholder
        return {
            "summary": "Validation summary would be generated based on previous validation steps",
            "status": "pending"
        }

    def cleanup_temp_database(self) -> Dict:
        """Clean up temporary database resources"""
        if self.temp_db_path:
            try:
                import os
                os.unlink(self.temp_db_path)
                self.temp_db_path = None
                return {"success": True, "message": "Temporary database cleaned up"}
            except Exception as e:
                return {"success": False, "error": f"Failed to cleanup: {str(e)}"}
        else:
            return {"success": True, "message": "No temporary database to clean up"}

    def validate_changeset(self, changeset: Dict) -> Dict:
        """Main validation method - runs comprehensive validation"""
        self.logger.log_step("Starting comprehensive changeset validation")
        self.logger.log_thinking("Analyzing changeset structure and preparing validation pipeline...")
        
        log_json_pretty(self.logger, "CHANGESET TO VALIDATE", changeset, "INFO")
        
        try:
            validation_results = {
                "valid": True,
                "errors": [],
                "warnings": [],
                "summary": {},
                "suggestions": []
            }
            
            self.logger.log_step("Initialized validation results structure")
            
            # Create temporary database
            self.logger.log_step("Creating temporary database for safe validation...")
            temp_result = self.create_temp_database()
            if not temp_result["success"]:
                error_result = {"valid": False, "error": temp_result["error"]}
                self.logger.log_step("Temporary database creation failed - aborting validation")
                return error_result
            
            self.logger.log_step("Temporary database created successfully")
            
            # Generate diff first
            self.logger.log_step("Generating diff to show what changes would be made...")
            diff_result = self.generate_diff(changeset)
            if diff_result["success"]:
                validation_results["summary"]["diff"] = diff_result["diff"]
                self.logger.log_step("Diff generated successfully", {
                    "total_operations": diff_result["diff"].get("total_operations", 0)
                })
            else:
                self.logger.log_step("Diff generation failed", {"error": diff_result.get("error")})
            
            # Validate required fields before applying
            self.logger.log_step("Validating required fields...")
            required_result = self.validate_required_fields(changeset)
            if not required_result["valid"]:
                validation_results["valid"] = False
                validation_results["errors"].extend(required_result["errors"])
                self.logger.log_validation("Required fields", False, {
                    "error_count": len(required_result["errors"])
                })
            else:
                self.logger.log_validation("Required fields", True)
            
            # Validate data types
            self.logger.log_step("Validating data types...")
            type_result = self.validate_data_types(changeset)
            if not type_result["valid"]:
                validation_results["valid"] = False
                validation_results["errors"].extend(type_result["errors"])
                self.logger.log_validation("Data types", False, {
                    "error_count": len(type_result["errors"])
                })
            else:
                self.logger.log_validation("Data types", True)
            
            # Apply changeset to temporary database
            if validation_results["valid"]:
                self.logger.log_step("Pre-validation checks passed - applying changeset to temporary database...")
                apply_result = self.apply_changeset(changeset)
                if not apply_result["success"]:
                    validation_results["valid"] = False
                    validation_results["errors"].extend(apply_result["errors"])
                    self.logger.log_validation("Changeset application", False, {
                        "error_count": len(apply_result["errors"])
                    })
                else:
                    validation_results["summary"]["applied_operations"] = len(apply_result["applied_operations"])
                    self.logger.log_validation("Changeset application", True, {
                        "operations_applied": len(apply_result["applied_operations"])
                    })
                    
                    # Run post-application validations
                    self.logger.log_step("Running post-application validations...")
                    
                    # Foreign key validation
                    self.logger.log_step("Checking foreign key constraints...")
                    fk_result = self.validate_foreign_keys()
                    if not fk_result["valid"]:
                        validation_results["valid"] = False
                        validation_results["errors"].append({
                            "type": "foreign_key_violations",
                            "violations": fk_result["violations"]
                        })
                        self.logger.log_validation("Foreign key constraints", False, {
                            "violation_count": len(fk_result["violations"])
                        })
                    else:
                        self.logger.log_validation("Foreign key constraints", True)
                    
                    # Unique constraint validation
                    self.logger.log_step("Checking unique constraints...")
                    unique_result = self.validate_unique_constraints()
                    if not unique_result["valid"]:
                        validation_results["valid"] = False
                        validation_results["errors"].append({
                            "type": "unique_constraint_violations", 
                            "violations": unique_result["violations"]
                        })
                        self.logger.log_validation("Unique constraints", False, {
                            "violation_count": len(unique_result["violations"])
                        })
                    else:
                        self.logger.log_validation("Unique constraints", True)
                    
                    # Referential integrity validation
                    self.logger.log_step("Checking referential integrity...")
                    integrity_result = self.check_referential_integrity()
                    if not integrity_result["valid"]:
                        validation_results["valid"] = False
                        validation_results["errors"].append({
                            "type": "referential_integrity_issues",
                            "issues": integrity_result["issues"]
                        })
                        self.logger.log_validation("Referential integrity", False, {
                            "issue_count": len(integrity_result["issues"])
                        })
                    else:
                        self.logger.log_validation("Referential integrity", True)
            else:
                self.logger.log_step("Pre-validation checks failed - skipping changeset application")
            
            # Add suggestions for common issues
            if not validation_results["valid"]:
                self.logger.log_step("Validation failed - generating suggestions", {
                    "total_errors": len(validation_results["errors"])
                })
                validation_results["suggestions"] = [
                    "Check that all referenced IDs exist in their respective tables",
                    "Ensure required fields are provided for INSERT operations",
                    "Verify data types match the expected schema",
                    "Use placeholder IDs (starting with $) for new records that reference each other"
                ]
            else:
                self.logger.log_step("All validations passed successfully! ✅")
            
            # Final validation summary
            final_summary = {
                "total_errors": len(validation_results["errors"]),
                "total_warnings": len(validation_results["warnings"]),
                "validation_passed": validation_results["valid"]
            }
            
            self.logger.log_step("Validation complete", final_summary)
            log_json_pretty(self.logger, "VALIDATION RESULTS", validation_results, "INFO")
            
            # Cleanup
            cleanup_result = self.cleanup_temp_database()
            self.logger.log_step("Cleanup completed", cleanup_result)
            
            return validation_results
            
        except Exception as e:
            self.logger.log_error(e, "validate_changeset")
            # Ensure cleanup even on error
            cleanup_result = self.cleanup_temp_database()
            self.logger.log_step("Emergency cleanup completed", cleanup_result)
            return {"valid": False, "error": f"Validation failed: {str(e)}"}
        
    def __del__(self):
        """Cleanup on destruction"""
        if hasattr(self, 'logger'):
            self.logger.log_step("ValidatorAgent destructor called - cleaning up")
        self.cleanup_temp_database()