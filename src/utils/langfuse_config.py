"""
Langfuse Configuration for Enterprise Form Management Agent

This module sets up Langfuse integration for comprehensive observability
and evaluation of the agent system.
"""

import os
import logging
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from langfuse import Langfuse
import logfire

# Load environment variables
load_dotenv()

def setup_langfuse_logging(service_name: str = "enterprise_form_agent") -> bool:
    """
    Setup Langfuse logging and observability
    
    Args:
        service_name: Name of the service for tracing
        
    Returns:
        bool: True if setup successful, False otherwise
    """
    try:
        # Check for required environment variables
        public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
        secret_key = os.getenv("LANGFUSE_SECRET_KEY")
        host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
        
        if not public_key or not secret_key:
            logging.warning("Langfuse credentials not found. Set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY environment variables.")
            return False
        
        # Set up OpenTelemetry endpoint for Langfuse with proper authentication
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = f"{host}/api/public/otlp"
        
        # Set authorization headers for OpenTelemetry
        import base64
        # Build Basic Auth header.
        LANGFUSE_AUTH = base64.b64encode(
            f"{os.environ.get('LANGFUSE_PUBLIC_KEY')}:{os.environ.get('LANGFUSE_SECRET_KEY')}".encode()
        ).decode()
        
        # Configure OpenTelemetry endpoint & headers
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = os.environ.get("LANGFUSE_HOST") + "/api/public/otel"
        os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = f"Authorization=Basic {LANGFUSE_AUTH}"
        
        # Import and configure logfire (OpenTelemetry wrapper)
        try:
            # Configure logfire with Langfuse
            logfire.configure(
                service_name=service_name,
                send_to_logfire=False,  # We're sending to Langfuse instead
                console=False  # Disable console output to avoid duplication
            )
            
            # Instrument OpenAI agents
            logfire.instrument_openai_agents()
            
            logging.info(f"✅ Langfuse logging configured successfully for service: {service_name}")
            logging.info(f"   Host: {host}")
            logging.info(f"   Public Key: {public_key[:10]}...")
            
            return True
            
        except ImportError as e:
            logging.error(f"Failed to import logfire: {e}")
            logging.error("Install with: pip install logfire")
            return False
            
    except Exception as e:
        logging.error(f"Failed to setup Langfuse logging: {e}")
        return False

def get_langfuse_client():
    """
    Get Langfuse client for manual logging
    
    Returns:
        Langfuse client or None if not available
    """
    try:

        public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
        secret_key = os.getenv("LANGFUSE_SECRET_KEY")
        host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
        
        if not public_key or not secret_key:
            return None
            
        client = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host
        )
        return client
        
    except ImportError:
        logging.warning("Langfuse not installed. Install with: pip install langfuse")
        return None
    except Exception as e:
        logging.error(f"Failed to create Langfuse client: {e}")
        return None

def log_user_feedback(trace_id: str, score: float, comment: Optional[str] = None):
    """
    Log user feedback for a specific trace
    
    Args:
        trace_id: ID of the trace to provide feedback for
        score: Numerical score (0.0 to 1.0)
        comment: Optional text comment
    """
    client = get_langfuse_client()
    if client:
        try:
            client.score(
                trace_id=trace_id,
                name="user_feedback",
                value=score,
                comment=comment
            )
            logging.info(f"User feedback logged for trace {trace_id}: {score}")
        except Exception as e:
            logging.error(f"Failed to log user feedback: {e}")

def log_generation(trace_id: str, name: str, input_data: Any, output_data: Any, model: str, metadata: Optional[Dict[str, Any]] = None):
    """
    Log a generation (LLM call) to Langfuse
    
    Args:
        trace_id: ID of the parent trace
        name: Name of the generation
        input_data: Input to the LLM
        output_data: Output from the LLM
        model: Model name used
        metadata: Optional metadata
    """
    client = get_langfuse_client()
    if client:
        try:
            client.generation(
                trace_id=trace_id,
                name=name,
                input=input_data,
                output=output_data,
                model=model,
                metadata=metadata or {}
            )
            logging.debug(f"Generation logged: {name}")
        except Exception as e:
            logging.error(f"Failed to log generation: {e}")

def check_langfuse_status() -> Dict[str, Any]:
    """
    Check Langfuse configuration status
    
    Returns:
        Status dictionary with configuration details
    """
    status = {
        "configured": False,
        "client_available": False,
        "credentials_set": False,
        "host": os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
        "public_key_preview": None,
        "logfire_available": False
    }
    
    # Check credentials
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    
    if public_key and secret_key:
        status["credentials_set"] = True
        status["public_key_preview"] = f"{public_key[:10]}..."
    
    # Check client
    client = get_langfuse_client()
    if client:
        status["client_available"] = True
    
    # Check logfire
    try:
        status["logfire_available"] = True
    except ImportError:
        pass
    
    status["configured"] = status["credentials_set"] and status["client_available"]
    
    return status