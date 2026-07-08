"""
Langfuse observability integration for monitoring LLM calls
(Optional - gracefully degrades if Langfuse not available)
"""

import os
from loguru import logger

# Try to import Langfuse, make it optional
try:
    from langfuse import Langfuse
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False
    logger.warning("Langfuse not available - observability disabled")


class ObservabilityManager:
    """Manages Langfuse tracing and metrics (optional)"""
    
    def __init__(self):
        self.enabled = False
        self.langfuse = None
        self.callback_handler = None
        self.current_session = None
        
        if not LANGFUSE_AVAILABLE:
            return
        
        # Initialize Langfuse client if credentials available
        try:
            public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "")
            secret_key = os.getenv("LANGFUSE_SECRET_KEY", "")
            
            if public_key and secret_key:
                self.langfuse = Langfuse(
                    public_key=public_key,
                    secret_key=secret_key,
                    host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
                )
                self.enabled = True
                logger.success("Langfuse observability enabled")
            else:
                logger.info("Langfuse credentials not found - observability disabled")
        except Exception as e:
            logger.warning(f"Could not initialize Langfuse: {e}")
    
    def start_session(self, session_id: str, metadata: dict = None):
        """Start a new tracing session"""
        if not self.enabled:
            return None
        
        try:
            self.current_session = self.langfuse.trace(
                name="story_generation",
                session_id=session_id,
                metadata=metadata or {}
            )
            return self.current_session
        except Exception as e:
            logger.warning(f"Langfuse session start failed: {e}")
            return None
    
    def log_agent_call(self, agent_name: str, input_data: dict, output_data: dict):
        """Log individual agent execution"""
        if not self.enabled or not self.current_session:
            return
        
        try:
            self.current_session.span(
                name=agent_name,
                input=input_data,
                output=output_data
            )
        except Exception as e:
            logger.warning(f"Langfuse logging failed: {e}")
    
    def log_metrics(self, metrics: dict):
        """Log quality metrics"""
        if not self.enabled or not self.current_session:
            return
        
        try:
            self.current_session.score(
                name="quality_score",
                value=metrics.get("quality_score", 0.0)
            )
            
            self.current_session.score(
                name="revision_count",
                value=metrics.get("revision_count", 0)
            )
        except Exception as e:
            logger.warning(f"Langfuse metrics logging failed: {e}")
    
    def end_session(self):
        """Finalize the session"""
        if not self.enabled or not self.current_session:
            return
        
        try:
            self.current_session.update(
                output={"status": "complete"}
            )
            self.langfuse.flush()
        except Exception as e:
            logger.warning(f"Langfuse session end failed: {e}")
    
    def get_dashboard_url(self):
        """Get URL to Langfuse dashboard"""
        if not self.enabled or not self.current_session:
            return None
        
        try:
            return f"{os.getenv('LANGFUSE_HOST', 'https://cloud.langfuse.com')}/trace/{self.current_session.id}"
        except:
            return None
