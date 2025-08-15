"""
Real-time File Logging System
Captures all SDK and custom logs to timestamped files for detailed analysis
"""

import os
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


class FileLoggingManager:
    """Manages real-time file logging for the entire agent system"""
    
    def __init__(self, logs_dir: str = "logs"):
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(exist_ok=True)
        
        # Create timestamped session
        self.session_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.logs_dir / f"session_{self.session_timestamp}"
        self.session_dir.mkdir(exist_ok=True)
        
        # File paths
        self.sdk_log_file = self.session_dir / "openai_agents_sdk.log"
        self.custom_log_file = self.session_dir / "custom_agents.log"
        self.combined_log_file = self.session_dir / "combined.log"
        
        # Store original handlers
        self.original_handlers = {}

    
    def setup_sdk_file_logging(self):
        """Setup file logging for OpenAI Agents SDK"""
        # Configure SDK loggers to write to files
        sdk_loggers = [
            "openai.agents",
            "openai.agents.tracing"
        ]
        
        for logger_name in sdk_loggers:
            logger = logging.getLogger(logger_name)
            
            # Store original handlers
            self.original_handlers[logger_name] = logger.handlers.copy()
            
            # Create file handler for SDK logs
            sdk_file_handler = logging.FileHandler(self.sdk_log_file, mode='a')
            sdk_file_handler.setLevel(logging.DEBUG)
            
            # Create formatter
            sdk_formatter = logging.Formatter(
                '%(asctime)s | %(name)s | %(levelname)s | %(message)s'
            )
            sdk_file_handler.setFormatter(sdk_formatter)
            
            # Add file handler
            logger.addHandler(sdk_file_handler)
            
            # Also add to combined log
            combined_handler = logging.FileHandler(self.combined_log_file, mode='a')
            combined_handler.setLevel(logging.DEBUG)
            combined_handler.setFormatter(sdk_formatter)
            logger.addHandler(combined_handler)
    
    def setup_custom_file_logging(self):
        """Setup file logging for all loggers at DEBUG level"""
        # Capture all logging at DEBUG level to session files
        root_logger = logging.getLogger()
        
        # Store original handlers
        self.original_handlers['root'] = root_logger.handlers.copy()
        
        # Add file handler to capture all logging to combined log
        combined_file_handler = logging.FileHandler(self.combined_log_file, mode='a')
        combined_file_handler.setLevel(logging.DEBUG)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s | %(name)s | %(levelname)s | %(message)s'
        )
        combined_file_handler.setFormatter(formatter)
        
        # Add handler to root logger to capture everything
        root_logger.addHandler(combined_file_handler)
        
        # Set root logger to DEBUG level to capture all messages
        if root_logger.level > logging.DEBUG:
            root_logger.setLevel(logging.DEBUG)
    
    def setup_console_minimal_logging(self):
        """Setup minimal console logging - only show important messages"""
        # Create a custom console handler that filters messages
        class MinimalConsoleHandler(logging.StreamHandler):
            def emit(self, record):
                # Only show important messages on console
                important_keywords = [
                    "QUERY START", "QUERY", "SUCCESS", "FAILED", "ERROR", 
                    "STEP:", "THINKING:", "TOOL CALL:", "VALIDATION"
                ]
                
                if any(keyword in record.getMessage() for keyword in important_keywords):
                    super().emit(record)
        
        # Apply to our custom loggers
        custom_logger_names = [
            "MasterAgent",
            "ValidatorAgent", 
            "AskClarificationAgent",
            "ContextMemory"
        ]
        
        for logger_name in custom_logger_names:
            logger = logging.getLogger(logger_name)
            
            # Remove existing console handlers
            logger.handlers = [h for h in logger.handlers if not isinstance(h, logging.StreamHandler)]
            
            # Add minimal console handler
            minimal_handler = MinimalConsoleHandler(sys.stdout)
            minimal_handler.setLevel(logging.INFO)
            minimal_formatter = logging.Formatter('🤖 %(name)s | %(levelname)s | %(message)s')
            minimal_handler.setFormatter(minimal_formatter)
            logger.addHandler(minimal_handler)
    
    def setup_all_logging(self, minimal_console: bool = True):
        """Setup complete file logging system"""
        print("🔧 Setting up real-time file logging...")
        
        # Setup file logging
        self.setup_sdk_file_logging()
        self.setup_custom_file_logging()
        
        if minimal_console:
            self.setup_console_minimal_logging()
        
        # Write session header to files
        header = f"""
========================================
AGENT SYSTEM LOGGING SESSION
Started: {datetime.now().isoformat()}
Session ID: {self.session_timestamp}
========================================

"""
        
        for log_file in [self.sdk_log_file, self.custom_log_file, self.combined_log_file]:
            with open(log_file, 'a') as f:
                f.write(header)
    
    def cleanup(self):
        """Restore original logging configuration"""
        print("\n🔧 Cleaning up file logging...")
        
        for logger_name, original_handlers in self.original_handlers.items():
            logger = logging.getLogger(logger_name)
            logger.handlers.clear()
            logger.handlers.extend(original_handlers)
        
        print("✅ Logging cleanup complete")
    
    def get_session_info(self):
        """Get information about the current logging session"""
        return {
            "session_id": self.session_timestamp,
            "session_dir": str(self.session_dir),
            "sdk_log": str(self.sdk_log_file),
            "custom_log": str(self.custom_log_file),
            "combined_log": str(self.combined_log_file)
        }
    
    def tail_command(self):
        """Get the tail command to follow logs in real-time"""
        return f"tail -f {self.combined_log_file}"


# Global instance
_file_logger: Optional[FileLoggingManager] = None


def get_file_logger() -> Optional[FileLoggingManager]:
    """Get the global file logger instance"""
    return _file_logger


def setup_file_logging(logs_dir: str = "logs", minimal_console: bool = True) -> FileLoggingManager:
    """Setup file logging system"""
    global _file_logger
    _file_logger = FileLoggingManager(logs_dir)
    _file_logger.setup_all_logging(minimal_console)
    return _file_logger


def cleanup_file_logging():
    """Cleanup file logging system"""
    global _file_logger
    if _file_logger:
        _file_logger.cleanup()
        _file_logger = None