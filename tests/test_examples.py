import pytest
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.agent.workflow import FormAgentWorkflow

class TestExampleQueries:
    """Test cases based on the provided examples"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.agent = FormAgentWorkflow(model_provider="openai")
    
    def test_update_dropdown_options(self):
        """Test: update dropdown options for destination field"""
        query = "update the dropdown options for the destinations field in the travel request form: 1. add a paris option, 2. change tokyo to wuhan"
        
        result = self.agent.process_query(query)
        
        # Should not have errors
        assert "error" not in result
        
        # Should have option_items changes
        assert "option_items" in result
        
        # Should have insert and update operations
        option_ops = result["option_items"]
        assert "insert" in option_ops
        assert "update" in option_ops
        
        # Check insert operation for Paris
        paris_insert = next((item for item in option_ops["insert"] if "paris" in item["value"].lower()), None)
        assert paris_insert is not None
        assert paris_insert["value"] == "Paris"
        assert paris_insert["label"] == "Paris"
        
        # Check update operation for Tokyo -> Wuhan
        wuhan_update = next((item for item in option_ops["update"] if "wuhan" in item["value"].lower()), None)
        assert wuhan_update is not None
        assert wuhan_update["value"] == "Wuhan"
        assert wuhan_update["label"] == "Wuhan"
    
    def test_add_conditional_logic(self):
        """Test: require university_name when employment_status is Student"""
        query = "I want the employment-demo form to require university_name when employment_status is Student. University name should be a text field"
        
        result = self.agent.process_query(query)
        
        # Should not have errors  
        assert "error" not in result
        
        # Should create form field
        assert "form_fields" in result
        assert "insert" in result["form_fields"]
        
        # Should create logic rule
        assert "logic_rules" in result
        assert "insert" in result["logic_rules"]
        
        # Should create conditions and actions
        assert "logic_conditions" in result
        assert "logic_actions" in result
        
        # Check field creation
        field = result["form_fields"]["insert"][0]
        assert field["code"] == "university_name"
        assert field["type_id"] == 1  # short_text
        
        # Check logic rule
        rule = result["logic_rules"]["insert"][0]
        assert "university_name" in rule["name"].lower()
        
        # Check condition for employment_status = Student
        condition = result["logic_conditions"]["insert"][0]
        assert condition["operator"] == "="
        assert "Student" in condition["rhs"]
        
        # Check actions (show and require)
        actions = result["logic_actions"]["insert"]
        assert len(actions) == 2
        
        show_action = next((a for a in actions if a["action"] == "show"), None)
        require_action = next((a for a in actions if a["action"] == "require"), None)
        
        assert show_action is not None
        assert require_action is not None

class TestEdgeCases:
    """Test edge cases and error conditions"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.agent = FormAgentWorkflow(model_provider="openai")
    
    def test_nonexistent_form(self):
        """Test query with non-existent form"""
        query = "add a field to the nonexistent-form"
        
        result = self.agent.process_query(query)
        
        # Should trigger clarification or error
        assert "clarification_needed" in result or "error" in result
    
    def test_ambiguous_query(self):
        """Test very ambiguous query"""
        query = "change something"
        
        result = self.agent.process_query(query)
        
        # Should trigger clarification
        assert "clarification_needed" in result
        assert "questions" in result
        assert len(result["questions"]) > 0
    
    def test_malformed_query(self):
        """Test query that doesn't make sense"""
        query = "asdf jklm random text 123"
        
        result = self.agent.process_query(query)
        
        # Should handle gracefully
        assert "error" in result or "clarification_needed" in result

class TestValidation:
    """Test validation logic"""
    
    def setup_method(self):
        """Setup test fixtures"""
        from src.agent.validator import ChangeValidator
        self.validator = ChangeValidator()
    
    def test_valid_changeset(self):
        """Test validation of valid changeset"""
        changes = {
            "option_items": {
                "insert": [
                    {
                        "id": "$opt_paris",
                        "option_set_id": "existing-option-set-id",
                        "value": "Paris",
                        "label": "Paris",
                        "position": 6,
                        "is_active": 1
                    }
                ]
            }
        }
        
        errors = self.validator.validate_changes(changes)
        # May have foreign key errors since we're not using real IDs
        # But should not have structural errors
        structural_errors = [e for e in errors if "Missing required fields" in e or "must be" in e]
        assert len(structural_errors) == 0
    
    def test_missing_required_fields(self):
        """Test validation catches missing required fields"""
        changes = {
            "form_fields": {
                "insert": [
                    {
                        "id": "$fld_test"
                        # Missing required fields: form_id, type_id, code, label, position
                    }
                ]
            }
        }
        
        errors = self.validator.validate_changes(changes)
        
        # Should catch missing required fields
        missing_field_errors = [e for e in errors if "Missing required fields" in e]
        assert len(missing_field_errors) > 0

if __name__ == "__main__":
    pytest.main([__file__])