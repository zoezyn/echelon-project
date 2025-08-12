from typing import Dict, Any, List, Tuple
import json
from enum import Enum

class EvaluationMetric(str, Enum):
    STRUCTURAL_CORRECTNESS = "structural_correctness"
    SEMANTIC_ACCURACY = "semantic_accuracy" 
    COMPLETENESS = "completeness"
    IDEMPOTENCY = "idempotency"
    FOREIGN_KEY_INTEGRITY = "foreign_key_integrity"

class AgentEvaluator:
    """Evaluates agent performance against ground truth examples"""
    
    def __init__(self):
        self.ground_truth_examples = self._load_ground_truth()
    
    def _load_ground_truth(self) -> List[Dict[str, Any]]:
        """Load ground truth test cases"""
        return [
            {
                "query": "update the dropdown options for the destination field in the travel request form: 1. add a paris option, 2. change tokyo to wuhan",
                "expected_output": {
                    "option_items": {
                        "insert": [
                            {
                                "id": "$opt_paris",
                                "option_set_id": "a930a282-9b59-4099-be59-e4b16fb73ff5",
                                "value": "Paris",
                                "label": "Paris", 
                                "position": 6,
                                "is_active": 1
                            }
                        ],
                        "update": [
                            {
                                "id": "1aef8211-2dc0-410d-86f7-87aa84b60416",
                                "value": "Wuhan",
                                "label": "Wuhan"
                            }
                        ]
                    }
                }
            },
            {
                "query": "I want the employment-demo form to require university_name when employment_status is Student. University name should be a text field",
                "expected_output": {
                    "form_fields": {
                        "insert": [
                            {
                                "id": "$fld_university_name",
                                "form_id": "b061ee07-1842-416a-b166-3efdb0307642",
                                "page_id": "73aeda74-b227-4155-86d1-018a65bd3e28",
                                "type_id": 1,
                                "code": "university_name",
                                "label": "University name",
                                "position": 4,
                                "required": 0,
                                "read_only": 0,
                                "placeholder": "Your university",
                                "visible_by_default": 0
                            }
                        ]
                    },
                    "logic_rules": {
                        "insert": [
                            {
                                "id": "$rule_student_uni",
                                "form_id": "b061ee07-1842-416a-b166-3efdb0307642",
                                "name": "Student requires university name",
                                "trigger": "on_change",
                                "scope": "form",
                                "priority": 10,
                                "enabled": 1
                            }
                        ]
                    },
                    "logic_conditions": {
                        "insert": [
                            {
                                "id": "$cond_student",
                                "rule_id": "$rule_student_uni",
                                "lhs_ref": "{\"type\":\"field\",\"field_id\":\"EXISTING_FIELD_ID_employment_status\",\"property\":\"value\"}",
                                "operator": "=",
                                "rhs": "\"Student\"",
                                "bool_join": "AND",
                                "position": 1
                            }
                        ]
                    },
                    "logic_actions": {
                        "insert": [
                            {
                                "id": "$act_show_uni",
                                "rule_id": "$rule_student_uni",
                                "action": "show",
                                "target_ref": "{\"type\":\"field\",\"field_id\":\"$fld_university_name\"}",
                                "params": None,
                                "position": 1
                            },
                            {
                                "id": "$act_require_uni", 
                                "rule_id": "$rule_student_uni",
                                "action": "require",
                                "target_ref": "{\"type\":\"field\",\"field_id\":\"$fld_university_name\"}",
                                "params": None,
                                "position": 2
                            }
                        ]
                    }
                }
            }
        ]
    
    def evaluate_response(self, query: str, actual_output: Dict[str, Any]) -> Dict[str, float]:
        """Evaluate a single response against ground truth"""
        
        # Find matching ground truth
        ground_truth = next(
            (gt for gt in self.ground_truth_examples if gt["query"] == query), 
            None
        )
        
        if not ground_truth:
            return {"error": "No ground truth found for query"}
        
        expected = ground_truth["expected_output"]
        
        scores = {}
        scores[EvaluationMetric.STRUCTURAL_CORRECTNESS] = self._evaluate_structural_correctness(actual_output, expected)
        scores[EvaluationMetric.SEMANTIC_ACCURACY] = self._evaluate_semantic_accuracy(actual_output, expected)
        scores[EvaluationMetric.COMPLETENESS] = self._evaluate_completeness(actual_output, expected)
        scores[EvaluationMetric.IDEMPOTENCY] = self._evaluate_idempotency(actual_output)
        scores[EvaluationMetric.FOREIGN_KEY_INTEGRITY] = self._evaluate_foreign_key_integrity(actual_output)
        
        # Overall score
        scores["overall"] = sum(scores.values()) / len(scores)
        
        return scores
    
    def _evaluate_structural_correctness(self, actual: Dict[str, Any], expected: Dict[str, Any]) -> float:
        """Evaluate if the JSON structure matches expectations"""
        
        if "error" in actual:
            return 0.0
        
        score = 0.0
        total_checks = 0
        
        # Check table presence
        for table in expected.keys():
            total_checks += 1
            if table in actual:
                score += 1
            
            # Check operation presence
            if table in actual:
                for operation in expected[table].keys():
                    total_checks += 1
                    if operation in actual[table]:
                        score += 1
        
        return score / max(total_checks, 1)
    
    def _evaluate_semantic_accuracy(self, actual: Dict[str, Any], expected: Dict[str, Any]) -> float:
        """Evaluate if the semantic content matches expectations"""
        
        if "error" in actual:
            return 0.0
        
        score = 0.0
        total_checks = 0
        
        for table, expected_ops in expected.items():
            if table not in actual:
                continue
                
            actual_ops = actual[table]
            
            for op_type, expected_records in expected_ops.items():
                if op_type not in actual_ops:
                    continue
                
                actual_records = actual_ops[op_type]
                
                # Check if expected records are present with correct key fields
                for expected_record in expected_records:
                    total_checks += 1
                    
                    # Look for matching record based on key fields
                    key_fields = self._get_key_fields(table, op_type, expected_record)
                    matching_record = self._find_matching_record(actual_records, key_fields, expected_record)
                    
                    if matching_record:
                        score += 1
        
        return score / max(total_checks, 1)
    
    def _evaluate_completeness(self, actual: Dict[str, Any], expected: Dict[str, Any]) -> float:
        """Evaluate if all expected changes are present"""
        
        if "error" in actual:
            return 0.0
        
        expected_changes = self._count_expected_changes(expected)
        actual_changes = self._count_actual_changes(actual)
        
        if expected_changes == 0:
            return 1.0
        
        # Penalize both missing and extra changes
        return max(0.0, 1.0 - abs(actual_changes - expected_changes) / expected_changes)
    
    def _evaluate_idempotency(self, actual: Dict[str, Any]) -> float:
        """Evaluate if changes follow idempotency principles"""
        
        if "error" in actual:
            return 0.0
        
        score = 1.0
        
        # Check that updates/deletes use real IDs, not placeholders
        for table, operations in actual.items():
            for op_type in ['update', 'delete']:
                if op_type in operations:
                    for record in operations[op_type]:
                        if 'id' in record and record['id'].startswith('$'):
                            score -= 0.2  # Deduct for placeholder ID in update/delete
        
        return max(0.0, score)
    
    def _evaluate_foreign_key_integrity(self, actual: Dict[str, Any]) -> float:
        """Evaluate if foreign key references are valid"""
        
        if "error" in actual:
            return 0.0
        
        # This is a simplified check - in practice would validate against actual DB
        score = 1.0
        
        # Check for obvious FK violations (placeholder references to non-existent placeholders)
        defined_placeholders = set()
        referenced_placeholders = set()
        
        # Collect defined placeholders
        for table, operations in actual.items():
            if 'insert' in operations:
                for record in operations['insert']:
                    if 'id' in record and record['id'].startswith('$'):
                        defined_placeholders.add(record['id'])
        
        # Collect referenced placeholders
        for table, operations in actual.items():
            for op_type, records in operations.items():
                for record in records:
                    for key, value in record.items():
                        if key.endswith('_id') and isinstance(value, str) and value.startswith('$'):
                            referenced_placeholders.add(value)
        
        # Check if all referenced placeholders are defined
        undefined_refs = referenced_placeholders - defined_placeholders
        if undefined_refs:
            score -= len(undefined_refs) * 0.2
        
        return max(0.0, score)
    
    def _get_key_fields(self, table: str, op_type: str, record: Dict[str, Any]) -> List[str]:
        """Get key fields for record matching"""
        
        if op_type in ['update', 'delete']:
            return ['id']
        
        # For inserts, use semantic key fields
        key_mappings = {
            'option_items': ['value', 'option_set_id'],
            'form_fields': ['code', 'form_id'],
            'logic_rules': ['name', 'form_id'],
            'forms': ['slug']
        }
        
        return key_mappings.get(table, ['id'])
    
    def _find_matching_record(self, records: List[Dict[str, Any]], key_fields: List[str], expected: Dict[str, Any]) -> Dict[str, Any]:
        """Find matching record based on key fields"""
        
        for record in records:
            match = True
            for key_field in key_fields:
                if key_field not in expected or key_field not in record:
                    continue
                if record[key_field] != expected[key_field]:
                    match = False
                    break
            if match:
                return record
        
        return None
    
    def _count_expected_changes(self, expected: Dict[str, Any]) -> int:
        """Count total expected changes"""
        count = 0
        for table, operations in expected.items():
            for op_type, records in operations.items():
                count += len(records)
        return count
    
    def _count_actual_changes(self, actual: Dict[str, Any]) -> int:
        """Count total actual changes"""
        if "error" in actual or "clarification_needed" in actual:
            return 0
        
        count = 0
        for table, operations in actual.items():
            for op_type, records in operations.items():
                count += len(records)
        return count
    
    def run_baseline_evaluation(self, agent) -> Dict[str, Any]:
        """Run evaluation on all ground truth examples"""
        
        results = []
        
        for example in self.ground_truth_examples:
            query = example["query"]
            
            # Get agent response
            actual_output = agent.process_query(query)
            
            # Evaluate
            scores = self.evaluate_response(query, actual_output)
            
            results.append({
                "query": query,
                "scores": scores,
                "actual_output": actual_output
            })
        
        # Calculate aggregate scores
        aggregate_scores = {}
        for metric in EvaluationMetric:
            metric_scores = [r["scores"].get(metric, 0) for r in results if metric in r["scores"]]
            aggregate_scores[metric] = sum(metric_scores) / len(metric_scores) if metric_scores else 0
        
        overall_score = sum(aggregate_scores.values()) / len(aggregate_scores)
        
        return {
            "overall_score": overall_score,
            "metric_scores": aggregate_scores,
            "individual_results": results,
            "total_examples": len(results),
            "passed_examples": len([r for r in results if r["scores"].get("overall", 0) > 0.7])
        }