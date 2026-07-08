"""
LightRAG Client - HTTP Client for LightRAG Server API
Klien HTTP untuk LightRAG Server API

Based on LightRAG API at http://localhost:9621/
Docs: http://localhost:9621/redoc
"""

import httpx
import asyncio
from typing import Dict, List, Optional, Any, Literal
from pydantic import BaseModel, Field
from settings import LightRAGConfig
from loguru import logger


# =============================================================================
# Request/Response Models
# =============================================================================

class QueryRequest(BaseModel):
    """Request model for LightRAG query endpoint"""
    query: str = Field(min_length=3, description="The query text")
    mode: Literal["local", "global", "hybrid", "naive", "mix", "bypass"] = Field(
        default="hybrid",
        description="Query mode: local, global, hybrid, naive, mix, bypass"
    )
    only_need_context: Optional[bool] = Field(
        default=False,
        description="If True, only returns retrieved context without generating response"
    )
    top_k: Optional[int] = Field(
        default=5,
        ge=1,
        description="Number of top items to retrieve"
    )
    include_references: Optional[bool] = Field(
        default=True,
        description="Include reference list in response"
    )


class QueryResponse(BaseModel):
    """Response model from LightRAG query"""
    response: str = Field(description="Generated response")
    references: Optional[List[Dict[str, Optional[str]]]] = Field(
        default=None,
        description="Reference list with reference_id, file_path, and optional content"
    )


class InsertRequest(BaseModel):
    """Request model for inserting text into LightRAG"""
    text: str = Field(description="Text content to insert")
    description: Optional[str] = Field(default=None, description="Description for the document")


# =============================================================================
# LightRAG Client
# =============================================================================

class LightRAGClient:
    """
    HTTP Client for LightRAG Server.
    
    Provides methods to:
    - Query knowledge graph (local, global, hybrid modes)
    - Insert documents for indexing
    - Check server health
    
    Usage:
        client = LightRAGClient()
        
        # Query
        result = await client.query("What is photosynthesis?", mode="hybrid")
        
        # Insert content
        await client.insert("Photosynthesis is the process...")
    """
    
    def __init__(
        self,
        api_url: str = None,
        api_key: str = None,
        timeout: float = 60.0
    ):
        """
        Initialize LightRAG client.
        
        Args:
            api_url: LightRAG server URL (default from settings)
            api_key: Optional API key for authentication
            timeout: Request timeout in seconds
        """
        # Get API URL from param or settings
        url = api_url or LightRAGConfig.API_URL
        if not url:
            logger.warning("[LIGHTRAG::INIT] LIGHTRAG_API_URL not set in .env!")
            url = "http://localhost:9621"  # Fallback
        
        self.api_url = url.rstrip('/')
        self.api_key = api_key or LightRAGConfig.API_KEY
        self.timeout = timeout
        
        logger.info(f"[LIGHTRAG::INIT] Using API URL: {self.api_url}")
        
        # Build headers
        self.headers = {"Content-Type": "application/json"}
        if self.api_key:
            self.headers["Authorization"] = f"Bearer {self.api_key}"
    
    async def health_check(self) -> bool:
        """
        Check if LightRAG server is healthy.
        
        Returns:
            True if server is responding, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.api_url}/health")
                return response.status_code == 200
        except Exception:
            return False
    
    async def query(
        self,
        query: str,
        mode: Literal["local", "global", "hybrid", "naive", "mix", "bypass"] = None,
        only_need_context: bool = False,
        top_k: int = None,
        conversation_history: List[Dict[str, Any]] = None
    ) -> QueryResponse:
        """
        Query the LightRAG knowledge graph.
        
        Args:
            query: The query text
            mode: Query mode (default from settings)
            only_need_context: Return only retrieved context without LLM response
            top_k: Number of items to retrieve
            conversation_history: Optional conversation history for context
            
        Returns:
            QueryResponse with response and optional references
            
        Raises:
            httpx.HTTPStatusError: If request fails
        """
        # Build request body
        request_data = {
            "query": query,
            "mode": mode or LightRAGConfig.DEFAULT_MODE,
            "only_need_context": only_need_context,
            "top_k": top_k or LightRAGConfig.TOP_K,
            "include_references": True
        }
        
        if conversation_history:
            request_data["conversation_history"] = conversation_history
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.api_url}/query",
                json=request_data,
                headers=self.headers
            )
            response.raise_for_status()
            
            data = response.json()
            return QueryResponse(**data)
    
    async def query_context_only(
        self,
        query: str,
        mode: Literal["local", "global", "hybrid"] = "hybrid",
        top_k: int = None
    ) -> str:
        """
        Get only the retrieved context without LLM generation.
        Useful for injecting context into other prompts.
        
        Args:
            query: The query text
            mode: Query mode
            top_k: Number of items to retrieve
            
        Returns:
            Retrieved context as string
        """
        result = await self.query(
            query=query,
            mode=mode,
            only_need_context=True,
            top_k=top_k
        )
        return result.response
    
    async def insert_text(
        self,
        text: str,
        file_source: str = None
    ) -> Dict[str, Any]:
        """
        Insert text content into LightRAG for indexing.
        
        Args:
            text: Text content to insert
            file_source: Optional source identifier for the document
            
        Returns:
            Response from server with status and message
        """
        # LightRAG uses /documents/text endpoint for text insertion
        # API expects: {"text": str, "file_source": str (optional)}
        request_data = {
            "text": text
        }
        if file_source:
            request_data["file_source"] = file_source
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.api_url}/documents/text",
                json=request_data,
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
    
    async def insert_batch(
        self,
        texts: List[str],
        descriptions: List[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Insert multiple texts in batch.
        
        Args:
            texts: List of text contents
            descriptions: Optional list of descriptions
            
        Returns:
            List of responses
        """
        results = []
        descriptions = descriptions or [None] * len(texts)
        
        for text, desc in zip(texts, descriptions):
            result = await self.insert_text(text, desc)
            results.append(result)
            await asyncio.sleep(0.1)  # Rate limiting
        
        return results
    
    async def get_document_status(self, file_source: str) -> bool:
        """
        Check if a document exists in LightRAG by its file_source ID.
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Try query param filter (common convention) or list
                # Since we don't have exact API docs for "check", we assume /documents/ID or similar
                # User's LightRAG is at http://100.68.196.58:9621/
                
                # Try standard generic "get document by id" approach if ID is the file_source
                # Notes: LightRAG might not expose file_source as ID directly for GET.
                # But we can try to find it in the list if manageable.
                
                # Attempt 1: GET /documents/{id}
                resp = await client.get(f"{self.api_url}/documents/{file_source}", headers=self.headers)
                if resp.status_code == 200: return True
                
                # Attempt 2: GET /documents?file_source={id}
                resp = await client.get(f"{self.api_url}/documents", params={"file_source": file_source}, headers=self.headers)
                if resp.status_code == 200:
                   data = resp.json()
                   if isinstance(data, list) and len(data) > 0: return True

                return False
        except Exception:
            return False

    async def get_graph_info(self) -> Dict[str, Any]:
        """
        Get information about the knowledge graph.
        
        Returns:
            Graph statistics and metadata
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.api_url}/graph",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
    
    def query_sync(
        self,
        query: str,
        mode: Literal["local", "global", "hybrid", "naive", "mix", "bypass"] = None,
        **kwargs
    ) -> QueryResponse:
        """Synchronous wrapper for query()"""
        return asyncio.get_event_loop().run_until_complete(
            self.query(query, mode, **kwargs)
        )


# =============================================================================
# Singleton Instance
# =============================================================================

_lightrag_clients: Dict[str, LightRAGClient] = {}

def get_lightrag_client(language: str = "id") -> LightRAGClient:
    """
    Get or create singleton LightRAG client instance for a specific language.
    
    Args:
        language: Language code ("en" or "id" or full name like "Indonesian", "English")
    
    Returns:
        LightRAGClient instance mapped to correct port
    """
    global _lightrag_clients
    
    # Determine language key
    lang = str(language).lower()
    is_en = lang.startswith("en") or lang == "english" or lang == "inggris"
    key = "en" if is_en else "id"
    
    if key not in _lightrag_clients:
        url = "http://localhost:8631" if is_en else "http://localhost:8641"
        _lightrag_clients[key] = LightRAGClient(api_url=url)
        logger.info(f"[LIGHTRAG::INIT] Created Client for '{key}' on {url}")
        
    return _lightrag_clients[key]


# =============================================================================
# Test
# =============================================================================

if __name__ == "__main__":
    import asyncio
    
    async def test():
        client = LightRAGClient()
        
        # Test health check
        logger.info("Testing health check...")
        healthy = await client.health_check()
        logger.info(f"LightRAG Server healthy: {healthy}")
        
        if healthy:
            # Test query
            logger.info("Testing query...")
            result = await client.query(
                "What is photosynthesis?",
                mode="hybrid",
                top_k=3
            )
            logger.info(f"Response: {result.response[:200]}...")
            if result.references:
                logger.info(f"References: {len(result.references)}")
    
    asyncio.run(test())
