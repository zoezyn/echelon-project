"""
Guardrails for the Form Management AI Agent

This module provides comprehensive safety, security, and validation guardrails
to ensure the system operates safely and within acceptable boundaries.
"""

import re
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import logging
from dataclasses import dataclass

from .models import ParsedQuery, QueryIntent
from .logger import setup_logger

@dataclass
class GuardrailViolation:
    """Represents a guardrail violation"""
    severity: str  # 'critical', 'warning', 'info'
    category: str  # 'security', 'safety', 'validation', 'rate_limit', 'business_rule'
    message: str
    details: Optional[str] = None

class GuardrailEngine:
    """Main guardrail enforcement engine"""
    
    def __init__(self):
        self.logger = setup_logger("GuardrailEngine")
        
        # Configuration
        self.MAX_DAILY_CHANGES = 100
        self.MAX_BULK_OPERATIONS = 50
        self.RESTRICTED_TABLES = {'users', 'audit_logs', 'system_config'}
        self.PROTECTED_FIELDS = {'password', 'api_key', 'secret', 'token'}
        
        # Rate limiting state (in production, use Redis/database)
        self.daily_change_count = 0
        self.last_reset_date = datetime.now().date()
    
    def validate_query(self, parsed_query: ParsedQuery, context: Dict[str, Any]) -> List[GuardrailViolation]:
        """Validate a parsed query against all guardrails"""
        violations = []
        
        # Security guardrails
        violations.extend(self._check_security_violations(parsed_query, context))
        
        # Safety guardrails
        violations.extend(self._check_safety_violations(parsed_query, context))
        
        # Business rule guardrails
        violations.extend(self._check_business_rules(parsed_query, context))
        
        # Rate limiting guardrails
        violations.extend(self._check_rate_limits(parsed_query, context))
        
        return violations
    
    def validate_changes(self, changes: Dict[str, Any], context: Dict[str, Any] = None) -> List[GuardrailViolation]:
        """Comprehensive validation of generated database changes"""
        violations = []
        
        # Technical validation (structure, format, required fields)
        violations.extend(self._check_technical_validity(changes))
        
        # Security validation
        violations.extend(self._check_change_safety(changes))
        
        # Data integrity validation
        # violations.extend(self._check_data_integrity(changes, context))
        
        # Business rules validation
        violations.extend(self._check_business_rules_changes(changes, context))
        
        # Operational safety
        violations.extend(self._check_bulk_operations(changes))
        
        return violations
    
    def _check_security_violations(self, parsed_query: ParsedQuery, context: Dict[str, Any]) -> List[GuardrailViolation]:
        """Check for security-related violations"""
        violations = []
        
        # 1. Prevent access to restricted tables
        if any(table in str(parsed_query.form_identifier).lower() for table in self.RESTRICTED_TABLES):
            violations.append(GuardrailViolation(
                severity='critical',
                category='security',
                message='Access to system tables is not allowed',
                details=f'Attempted access to restricted table: {parsed_query.form_identifier}'
            ))
        
        # 2. Check for SQL injection patterns in user input
        suspicious_patterns = [
            r'(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER)\b)',
            r'(--|\;|\|)',
            r'(\bUNION\b.*\bSELECT\b)',
            r'(\bOR\b.*=.*\bOR\b)',
            r'(\'\s*(OR|AND)\s*\'\s*=\s*\')',
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, str(parsed_query.model_dump()), re.IGNORECASE):
                violations.append(GuardrailViolation(
                    severity='critical',
                    category='security',
                    message='Potential SQL injection attempt detected',
                    details=f'Suspicious pattern found: {pattern}'
                ))
        
        # 3. Prevent access to protected field types
        if parsed_query.field_code and any(protected in parsed_query.field_code.lower() for protected in self.PROTECTED_FIELDS):
            violations.append(GuardrailViolation(
                severity='critical',
                category='security',
                message='Access to protected fields is not allowed',
                details=f'Attempted access to protected field: {parsed_query.field_code}'
            ))
        
        return violations
    
    def _check_safety_violations(self, parsed_query: ParsedQuery, context: Dict[str, Any]) -> List[GuardrailViolation]:
        """Check for safety-related violations"""
        violations = []
        
        # 1. Prevent deletion of critical forms
        if parsed_query.intent == QueryIntent.DELETE_FORM:
            form = context.get('form', {})
            if form.get('status') == 'published':
                violations.append(GuardrailViolation(
                    severity='critical',
                    category='safety',
                    message='Cannot delete published forms through AI agent',
                    details='Published forms must be manually archived by administrators'
                ))
        
        # 2. Prevent deletion of fields with existing data
        if parsed_query.intent == QueryIntent.DELETE_FIELD:
            violations.append(GuardrailViolation(
                severity='warning',
                category='safety',
                message='Field deletion requires manual verification',
                details='Deleting fields may cause data loss. Please verify no submissions exist.'
            ))
        
        # 3. Validate form status changes
        if parsed_query.intent == QueryIntent.UPDATE_FORM:
            if parsed_query.parameters and parsed_query.parameters.get('status') == 'published':
                violations.append(GuardrailViolation(
                    severity='warning',
                    category='safety',
                    message='Publishing forms requires manual review',
                    details='Form publishing should be reviewed by administrators'
                ))
        
        return violations
    
    def _check_business_rules(self, parsed_query: ParsedQuery, context: Dict[str, Any]) -> List[GuardrailViolation]:
        """Check business rule violations"""
        violations = []
        
        # 1. Limit number of options per field
        if parsed_query.intent == QueryIntent.ADD_OPTIONS:
            existing_options = context.get('field_options', [])
            if len(existing_options) >= 50:
                violations.append(GuardrailViolation(
                    severity='warning',
                    category='business_rule',
                    message='Too many options for dropdown field',
                    details='Consider using a different field type for fields with 50+ options'
                ))
        
        # 2. Validate field naming conventions
        if parsed_query.field_code:
            if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', parsed_query.field_code):
                violations.append(GuardrailViolation(
                    severity='warning',
                    category='business_rule',
                    message='Invalid field code format',
                    details='Field codes must start with a letter and contain only letters, numbers, and underscores'
                ))
        
        # 3. Prevent duplicate field codes
        if parsed_query.intent == QueryIntent.ADD_FIELD:
            existing_fields = context.get('form_fields', [])
            existing_codes = [f.get('code') for f in existing_fields]
            if parsed_query.field_code in existing_codes:
                violations.append(GuardrailViolation(
                    severity='critical',
                    category='business_rule',
                    message='Duplicate field code not allowed',
                    details=f'Field code "{parsed_query.field_code}" already exists in this form'
                ))
        
        return violations
    
    def _check_rate_limits(self, parsed_query: ParsedQuery, context: Dict[str, Any]) -> List[GuardrailViolation]:
        """Check rate limiting violations"""
        violations = []
        
        # Reset daily counter if needed
        today = datetime.now().date()
        if today > self.last_reset_date:
            self.daily_change_count = 0
            self.last_reset_date = today
        
        # Check daily change limit
        if self.daily_change_count >= self.MAX_DAILY_CHANGES:
            violations.append(GuardrailViolation(
                severity='critical',
                category='rate_limit',
                message='Daily change limit exceeded',
                details=f'Maximum {self.MAX_DAILY_CHANGES} changes per day allowed'
            ))
        
        return violations
    
    def _check_change_safety(self, changes: Dict[str, Any]) -> List[GuardrailViolation]:
        """Check safety of generated database changes"""
        violations = []
        
        # 1. Prevent changes to system tables
        for table_name in changes.keys():
            if table_name in self.RESTRICTED_TABLES:
                violations.append(GuardrailViolation(
                    severity='critical',
                    category='security',
                    message=f'Changes to system table "{table_name}" are not allowed'
                ))
        
        # 2. Validate required fields
        for table_name, operations in changes.items():
            if 'insert' in operations:
                for record in operations['insert']:
                    violations.extend(self._validate_required_fields(table_name, record))
        
        return violations
    
    def _check_data_integrity(self, changes: Dict[str, Any]) -> List[GuardrailViolation]:
        """Check data integrity constraints"""
        violations = []
        
        # 1. Validate foreign key references
        for table_name, operations in changes.items():
            for op_type in ['insert', 'update']:
                if op_type in operations:
                    for record in operations[op_type]:
                        violations.extend(self._validate_foreign_keys(table_name, record))
        
        # 2. Check for orphaned records
        if 'forms' in changes and 'delete' in changes['forms']:
            violations.append(GuardrailViolation(
                severity='warning',
                category='validation',
                message='Form deletion may create orphaned records',
                details='Ensure all related fields, pages, and rules are also handled'
            ))
        
        return violations
    
    def _check_bulk_operations(self, changes: Dict[str, Any]) -> List[GuardrailViolation]:
        """Check for excessive bulk operations"""
        violations = []
        
        total_operations = 0
        for table_name, operations in changes.items():
            for op_type in ['insert', 'update', 'delete']:
                if op_type in operations:
                    total_operations += len(operations[op_type])
        
        if total_operations > self.MAX_BULK_OPERATIONS:
            violations.append(GuardrailViolation(
                severity='warning',
                category='safety',
                message='Large bulk operation detected',
                details=f'Operation affects {total_operations} records. Consider breaking into smaller batches.'
            ))
        
        return violations
    
    def _validate_required_fields(self, table_name: str, record: Dict[str, Any]) -> List[GuardrailViolation]:
        """Validate required fields for a table"""
        violations = []
        
        required_fields = {
            'forms': ['id', 'title', 'slug'],
            'form_fields': ['id', 'form_id', 'code', 'label', 'type_id'],
            'option_items': ['id', 'option_set_id', 'value', 'label'],
            'logic_rules': ['id', 'form_id', 'name']
        }
        
        if table_name in required_fields:
            for field in required_fields[table_name]:
                if field not in record or not record[field]:
                    violations.append(GuardrailViolation(
                        severity='critical',
                        category='validation',
                        message=f'Required field "{field}" missing for table "{table_name}"'
                    ))
        
        return violations
    
    def _validate_foreign_keys(self, table_name: str, record: Dict[str, Any]) -> List[GuardrailViolation]:
        """Validate foreign key constraints"""
        violations = []
        
        # This is a simplified version - in production, you'd check actual database constraints
        foreign_key_rules = {
            'form_fields': ['form_id', 'type_id'],
            'option_items': ['option_set_id'],
            'logic_rules': ['form_id'],
            'logic_conditions': ['rule_id'],
            'logic_actions': ['rule_id']
        }
        
        if table_name in foreign_key_rules:
            for fk_field in foreign_key_rules[table_name]:
                if fk_field in record:
                    fk_value = record[fk_field]
                    # Skip placeholder references (start with $)
                    if not str(fk_value).startswith('$') and not fk_value:
                        violations.append(GuardrailViolation(
                            severity='critical',
                            category='validation',
                            message=f'Invalid foreign key reference in "{table_name}.{fk_field}"'
                        ))
        
        return violations
    
    def increment_daily_changes(self):
        """Increment the daily change counter"""
        self.daily_change_count += 1
    
    def has_critical_violations(self, violations: List[GuardrailViolation]) -> bool:
        """Check if there are any critical violations"""
        return any(v.severity == 'critical' for v in violations)
    
    def format_violations(self, violations: List[GuardrailViolation]) -> str:
        """Format violations into a user-friendly message"""
        if not violations:
            return ""
        
        critical = [v for v in violations if v.severity == 'critical']
        warnings = [v for v in violations if v.severity == 'warning']
        
        message = ""
        
        if critical:
            message += "❌ **Critical Issues:**\n"
            for v in critical:
                message += f"• {v.message}\n"
                if v.details:
                    message += f"  _{v.details}_\n"
            message += "\n"
        
        if warnings:
            message += "⚠️ **Warnings:**\n"
            for v in warnings:
                message += f"• {v.message}\n"
                if v.details:
                    message += f"  _{v.details}_\n"
        
        if critical:
            message += "\n**These critical issues must be resolved before proceeding.**"
        
        return message.strip()
    
    def _check_technical_validity(self, changes: Dict[str, Any]) -> List[GuardrailViolation]:
        """Check technical validity of change structure and format"""
        violations = []
        
        # Define required fields for each table
        required_fields = {
            'forms': ['id', 'slug', 'title'],
            'form_pages': ['id', 'form_id', 'position'],
            'form_fields': ['id', 'form_id', 'type_id', 'code', 'label', 'position'],
            'option_sets': ['id', 'name'],
            'option_items': ['id', 'option_set_id', 'value', 'label', 'position'],
            'field_option_binding': ['field_id', 'option_set_id'],
            'logic_rules': ['id', 'form_id', 'trigger', 'scope'],
            'logic_conditions': ['id', 'rule_id', 'lhs_ref', 'operator'],
            'logic_actions': ['id', 'rule_id', 'action', 'target_ref']
        }
        
        # Validate structure
        for table_name, operations in changes.items():
            if table_name not in required_fields:
                violations.append(GuardrailViolation(
                    severity='critical',
                    category='validation',
                    message=f'Unknown table: {table_name}'
                ))
                continue
            
            # Validate each operation type
            for op_type in ['insert', 'update', 'delete']:
                if op_type not in operations:
                    continue
                
                if not isinstance(operations[op_type], list):
                    violations.append(GuardrailViolation(
                        severity='critical',
                        category='validation',
                        message=f'Operation {op_type} in table {table_name} must be a list'
                    ))
                    continue
                
                for i, record in enumerate(operations[op_type]):
                    if not isinstance(record, dict):
                        violations.append(GuardrailViolation(
                            severity='critical',
                            category='validation',
                            message=f'Record {i} in {table_name}.{op_type} must be an object'
                        ))
                        continue
                    
                    # Validate required fields for inserts
                    if op_type == 'insert':
                        missing_fields = []
                        for field in required_fields[table_name]:
                            if field not in record:
                                missing_fields.append(field)
                        
                        if missing_fields:
                            violations.append(GuardrailViolation(
                                severity='critical',
                                category='validation',
                                message=f'Missing required fields in {table_name}: {missing_fields}'
                            ))
                    
                    # Validate ID is present for updates/deletes
                    if op_type in ['update', 'delete']:
                        if 'id' not in record:
                            violations.append(GuardrailViolation(
                                severity='critical',
                                category='validation',
                                message=f'Missing id field in {table_name}.{op_type} operation'
                            ))
                        elif record['id'].startswith('$'):
                            violations.append(GuardrailViolation(
                                severity='critical',
                                category='validation',
                                message=f'Update/delete operations cannot use placeholder IDs: {record["id"]}'
                            ))
        
        return violations
    
    def _check_business_rules_changes(self, changes: Dict[str, Any], context: Dict[str, Any] = None) -> List[GuardrailViolation]:
        """Check business rules for database changes"""
        violations = []
        
        # Validate form slugs are unique
        if 'forms' in changes:
            for form in changes['forms'].get('insert', []):
                slug = form.get('slug')
                if slug and context:
                    # Check if slug already exists
                    from .database import DatabaseManager
                    db = DatabaseManager()
                    with db.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT 1 FROM forms WHERE slug = ?", (slug,))
                        if cursor.fetchone():
                            violations.append(GuardrailViolation(
                                severity='critical',
                                category='business_rule',
                                message=f'Form slug "{slug}" already exists'
                            ))
        
        return violations