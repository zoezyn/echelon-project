from typing import Dict, Any, List
import json

from ..utils.database import DatabaseManager
from ..utils.logger import setup_logger

class ChangeValidator:
    def __init__(self):
        self.logger = setup_logger("ChangeValidator")
        self.db = DatabaseManager()
        
        # Define required fields for each table
        self.required_fields = {
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
    
    def validate_changes(self, changes: Dict[str, Any], context: Dict[str, Any] = None) -> List[str]:
        """Validate a change set and return list of errors"""
        self.logger.info("Validating change set")
        errors = []
        
        # Validate structure
        for table_name, operations in changes.items():
            if table_name not in self.required_fields:
                errors.append(f"Unknown table: {table_name}")
                continue
            
            # Validate each operation type
            for op_type in ['insert', 'update', 'delete']:
                if op_type not in operations:
                    continue
                
                if not isinstance(operations[op_type], list):
                    errors.append(f"Operation {op_type} in table {table_name} must be a list")
                    continue
                
                for i, record in enumerate(operations[op_type]):
                    if not isinstance(record, dict):
                        errors.append(f"Record {i} in {table_name}.{op_type} must be an object")
                        continue
                    
                    # Validate required fields for inserts
                    if op_type == 'insert':
                        missing_fields = []
                        for field in self.required_fields[table_name]:
                            if field not in record:
                                missing_fields.append(field)
                        
                        if missing_fields:
                            errors.append(f"Missing required fields in {table_name}.insert[{i}]: {missing_fields}")
                    
                    # Validate ID is present for updates/deletes
                    if op_type in ['update', 'delete']:
                        if 'id' not in record:
                            errors.append(f"Missing id field in {table_name}.{op_type}[{i}]")
                        elif record['id'].startswith('$'):
                            errors.append(f"Update/delete operations cannot use placeholder IDs: {record['id']}")
        
        # Validate foreign key references exist in database
        db_errors = self.db.validate_foreign_keys(changes)
        errors.extend(db_errors)
        
        # Validate specific business rules
        errors.extend(self._validate_business_rules(changes, context))
        
        if errors:
            self.logger.warning(f"Validation found {len(errors)} errors: {errors}")
        else:
            self.logger.info("Validation passed - no errors found")
        
        return errors
    
    def _validate_business_rules(self, changes: Dict[str, Any], context: Dict[str, Any] = None) -> List[str]:
        """Validate business-specific rules"""
        errors = []
        
        # Validate option set bindings
        if 'field_option_binding' in changes:
            for binding in changes['field_option_binding'].get('insert', []):
                field_id = binding.get('field_id')
                option_set_id = binding.get('option_set_id')
                
                # Check if field supports options
                if context and 'form_fields' in context:
                    field_info = next((f for f in context['form_fields'] if f['id'] == field_id), None)
                    if field_info and not field_info.get('has_options'):
                        errors.append(f"Field {field_id} does not support options")
        
        # Validate logic rule references
        if 'logic_conditions' in changes:
            for condition in changes['logic_conditions'].get('insert', []):
                lhs_ref = condition.get('lhs_ref')
                if lhs_ref:
                    try:
                        ref_obj = json.loads(lhs_ref)
                        if ref_obj.get('type') == 'field':
                            field_id = ref_obj.get('field_id')
                            # Validate field exists or is being created
                            if not self._field_exists_or_created(field_id, changes, context):
                                errors.append(f"Referenced field {field_id} does not exist")
                    except json.JSONDecodeError:
                        errors.append(f"Invalid lhs_ref format: {lhs_ref}")
        
        # Validate form slugs are unique
        if 'forms' in changes:
            for form in changes['forms'].get('insert', []):
                slug = form.get('slug')
                if slug and context:
                    # Check if slug already exists (simplified check)
                    with self.db.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT 1 FROM forms WHERE slug = ?", (slug,))
                        if cursor.fetchone():
                            errors.append(f"Form slug '{slug}' already exists")
        
        return errors
    
    def _field_exists_or_created(self, field_id: str, changes: Dict[str, Any], context: Dict[str, Any] = None) -> bool:
        """Check if field exists in database or is being created"""
        
        # Check if being created
        if 'form_fields' in changes:
            for field in changes['form_fields'].get('insert', []):
                if field.get('id') == field_id:
                    return True
        
        # Check if exists in context
        if context and 'form_fields' in context:
            for field in context['form_fields']:
                if field.get('id') == field_id:
                    return True
        
        # Check database (for non-placeholder IDs)
        if not field_id.startswith('$'):
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM form_fields WHERE id = ?", (field_id,))
                return cursor.fetchone() is not None
        
        return False