"""
Enhanced Logging Utility for Agent System
Provides detailed logging of agent reasoning and intermediate steps
"""

import logging
import json
import sys
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

class AgentLogger:
    """Enhanced logger for tracking agent thinking and operations"""
    
    def __init__(self, name: str, log_level: str = "INFO", log_to_file: bool = True):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        # Prevent duplicate handlers
        if not self.logger.handlers:
            self._setup_handlers(log_to_file)
    
    def _setup_handlers(self, log_to_file: bool):
        """Setup console and file handlers with proper formatting"""
        
        # Create formatters
        console_formatter = logging.Formatter(
            '🤖 %(name)s | %(levelname)s | %(message)s'
        )
        
        file_formatter = logging.Formatter(
            '%(asctime)s | %(name)s | %(levelname)s | %(message)s'
        )
        
        # Console handler for user-visible logs
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(logging.INFO)
        self.logger.addHandler(console_handler)
        
        # File handler for detailed debugging
        if log_to_file:
            log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)
            
            file_handler = logging.FileHandler(log_dir / f"{self.logger.name}.log")
            file_handler.setFormatter(file_formatter)
            file_handler.setLevel(logging.DEBUG)
            self.logger.addHandler(file_handler)
    
    def log_step(self, step: str, details: Dict[str, Any] = None, level: str = "INFO"):
        """Log an agent step with optional details"""
        message = f"STEP: {step}"
        if details:
            message += f" | Details: {json.dumps(details, indent=2)}"
        
        getattr(self.logger, level.lower())(message)
    
    def log_thinking(self, thought: str, level: str = "INFO"):
        """Log agent reasoning/thinking"""
        getattr(self.logger, level.lower())(f"THINKING: {thought}")
    
    def log_tool_call(self, tool_name: str, args: Dict[str, Any], level: str = "INFO"):
        """Log tool usage"""
        message = f"TOOL CALL: {tool_name}"
        if args:
            message += f" | Args: {json.dumps(args, indent=2)}"
        
        getattr(self.logger, level.lower())(message)
    
    def log_tool_result(self, tool_name: str, result: Any, level: str = "INFO"):
        """Log tool results"""
        if isinstance(result, (dict, list)):
            result_str = json.dumps(result, indent=2)
        else:
            result_str = str(result)
            
        getattr(self.logger, level.lower())(f"TOOL RESULT: {tool_name} | {result_str}")
    
    def log_query_start(self, query: str, context: Dict = None):
        """Log the start of query processing"""
        self.logger.info("=" * 80)
        self.logger.info(f"QUERY START: {query}")
        if context:
            self.logger.info(f"CONTEXT: {json.dumps(context, indent=2)}")
        self.logger.info("=" * 80)
    
    def log_query_end(self, result: Dict, success: bool = True):
        """Log the end of query processing"""
        status = "SUCCESS" if success else "FAILED"
        self.logger.info("=" * 80)
        self.logger.info(f"QUERY {status}")
        if result:
            self.logger.info(f"RESULT: {json.dumps(result, indent=2)}")
        self.logger.info("=" * 80)
    
    def log_agent_handoff(self, from_agent: str, to_agent: str, purpose: str):
        """Log agent handoffs"""
        self.logger.info(f"HANDOFF: {from_agent} -> {to_agent} | Purpose: {purpose}")
    
    def log_error(self, error: Exception, context: str = ""):
        """Log errors with context"""
        self.logger.error(f"ERROR in {context}: {str(error)}", exc_info=True)
    
    def log_validation(self, validation_type: str, passed: bool, details: Dict = None):
        """Log validation results"""
        status = "PASSED" if passed else "FAILED"
        message = f"VALIDATION {status}: {validation_type}"
        if details:
            message += f" | Details: {json.dumps(details, indent=2)}"
        
        level = "info" if passed else "warning"
        getattr(self.logger, level)(message)


def get_agent_logger(agent_name: str, log_level: str = "INFO") -> AgentLogger:
    """Factory function to get configured agent logger"""
    return AgentLogger(agent_name, log_level)


def log_json_pretty(logger: AgentLogger, label: str, data: Dict, level: str = "INFO"):
    """Helper to log JSON data in a pretty format"""
    try:
        pretty_json = json.dumps(data, indent=2, ensure_ascii=False)
        getattr(logger.logger, level.lower())(f"{label}:\n{pretty_json}")
    except Exception as e:
        logger.log_error(e, f"Failed to pretty print JSON for {label}")