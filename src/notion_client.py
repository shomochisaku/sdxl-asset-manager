"""
Notion API client for SDXL Asset Manager.

This module provides a comprehensive client for interacting with Notion API
with rate limiting, error handling, and async support.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from notion_client import Client
from notion_client.errors import (
    APIResponseError,
    HTTPResponseError,
    RequestTimeoutError,
)

# Configure logging
logger = logging.getLogger(__name__)


class NotionRateLimiter:
    """Rate limiter for Notion API (3 requests per second)."""

    def __init__(self, max_requests: int = 3, time_window: float = 1.0):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests: List[float] = []
        self._lock = asyncio.Lock()

    async def wait_if_needed(self) -> None:
        """Wait if rate limit would be exceeded."""
        async with self._lock:
            current_time = time.time()

            # Remove old requests outside time window
            self.requests = [
                req_time for req_time in self.requests
                if current_time - req_time < self.time_window
            ]

            # Check if we need to wait
            if len(self.requests) >= self.max_requests:
                oldest_request = min(self.requests)
                wait_time = self.time_window - (current_time - oldest_request)
                if wait_time > 0:
                    logger.debug(f"Rate limit: waiting {wait_time:.2f} seconds")
                    await asyncio.sleep(wait_time)

            # Record this request
            self.requests.append(current_time)


class NotionAPIError(Exception):
    """Base exception for Notion API errors."""
    pass


class NotionAuthenticationError(NotionAPIError):
    """Authentication error with Notion API."""
    pass


class NotionPermissionError(NotionAPIError):
    """Permission error with Notion API."""
    pass


class NotionRateLimitError(NotionAPIError):
    """Rate limit error with Notion API."""
    pass


class NotionTimeoutError(NotionAPIError):
    """Timeout error with Notion API."""
    pass


class NotionConnectionError(NotionAPIError):
    """Connection error with Notion API."""
    pass


class NotionClient:
    """
    Comprehensive Notion API client with rate limiting and error handling.

    Features:
    - Rate limiting (3 requests/second)
    - Automatic retry with exponential backoff
    - Comprehensive error handling
    - Async support for high-performance operations
    """

    def __init__(
        self,
        api_key: str,
        database_id: str,
        max_retries: int = 3,
        timeout: int = 30
    ):
        """
        Initialize Notion client.

        Args:
            api_key: Notion API key
            database_id: Target database ID
            max_retries: Maximum number of retry attempts
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.database_id = database_id
        self.max_retries = max_retries
        self.timeout = timeout

        # Initialize client and rate limiter
        self.client = Client(auth=api_key)
        self.rate_limiter = NotionRateLimiter()

        logger.info(f"Notion client initialized for database: {database_id}")

    async def _make_request(
        self,
        method: str,
        *args,
        **kwargs
    ) -> Any:
        """
        Make API request with rate limiting and error handling.

        Args:
            method: Method name to call on the client
            *args: Positional arguments for the method
            **kwargs: Keyword arguments for the method

        Returns:
            API response

        Raises:
            NotionAPIError: Various Notion API errors
        """
        for attempt in range(self.max_retries + 1):
            try:
                # Apply rate limiting
                await self.rate_limiter.wait_if_needed()

                # Get the method from client
                client_method = getattr(self.client, method)

                # Make the request
                logger.debug(f"Making Notion API request: {method} (attempt {attempt + 1})")
                response = client_method(*args, **kwargs)

                logger.debug(f"Notion API request successful: {method}")
                return response

            except RequestTimeoutError as e:
                logger.warning(f"Notion API timeout (attempt {attempt + 1}): {e}")
                if attempt >= self.max_retries:
                    raise NotionTimeoutError(f"タイムアウトエラー: {e}")
                await asyncio.sleep(2 ** attempt)

            except HTTPResponseError as e:
                if e.status == 401:
                    raise NotionAuthenticationError(f"認証エラー: APIキーが無効です - {e}")
                elif e.status == 403:
                    raise NotionPermissionError(f"権限エラー: データベースへのアクセス権限がありません - {e}")
                elif e.status == 429:
                    logger.warning(f"Rate limit exceeded (attempt {attempt + 1}): {e}")
                    if attempt >= self.max_retries:
                        raise NotionRateLimitError(f"レート制限エラー: {e}")
                    await asyncio.sleep(2 ** attempt)
                elif e.status >= 500:
                    # Server error - retry
                    logger.warning(f"Notion API server error (attempt {attempt + 1}): {e}")
                    if attempt >= self.max_retries:
                        raise NotionConnectionError(f"サーバーエラー: {e}")
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise NotionAPIError(f"APIエラー (HTTP {e.status}): {e}")

            except APIResponseError as e:
                logger.error(f"Notion API response error: {e}")
                raise NotionAPIError(f"APIレスポンスエラー: {e}")

            except Exception as e:
                logger.error(f"Unexpected error in Notion API request: {e}")
                raise NotionAPIError(f"予期しないエラー: {e}")

    async def get_database_info(self) -> Dict[str, Any]:
        """
        Get database information.

        Returns:
            Database information
        """
        return await self._make_request("databases.retrieve", database_id=self.database_id)

    async def get_database_pages(
        self,
        page_size: int = 100,
        start_cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get database pages with pagination.

        Args:
            page_size: Number of pages to retrieve (max 100)
            start_cursor: Start cursor for pagination

        Returns:
            Database pages response
        """
        query_params = {
            "database_id": self.database_id,
            "page_size": min(page_size, 100)
        }

        if start_cursor:
            query_params["start_cursor"] = start_cursor

        return await self._make_request("databases.query", **query_params)

    async def get_all_pages(self) -> List[Dict[str, Any]]:
        """
        Get all pages from the database.

        Returns:
            List of all pages
        """
        all_pages = []
        start_cursor = None

        while True:
            response = await self.get_database_pages(start_cursor=start_cursor)
            all_pages.extend(response.get("results", []))

            if not response.get("has_more", False):
                break

            start_cursor = response.get("next_cursor")

        logger.info(f"Retrieved {len(all_pages)} pages from database")
        return all_pages

    async def create_page(self, properties: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new page in the database.

        Args:
            properties: Page properties

        Returns:
            Created page response
        """
        page_data = {
            "parent": {"database_id": self.database_id},
            "properties": properties
        }

        response = await self._make_request("pages.create", **page_data)
        logger.info(f"Created page: {response.get('id')}")
        return response

    async def update_page(
        self,
        page_id: str,
        properties: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update a page in the database.

        Args:
            page_id: Page ID to update
            properties: Updated properties

        Returns:
            Updated page response
        """
        update_data = {
            "page_id": page_id,
            "properties": properties
        }

        response = await self._make_request("pages.update", **update_data)
        logger.info(f"Updated page: {page_id}")
        return response

    async def delete_page(self, page_id: str) -> Dict[str, Any]:
        """
        Delete (archive) a page.

        Args:
            page_id: Page ID to delete

        Returns:
            Deleted page response
        """
        update_data = {
            "page_id": page_id,
            "archived": True
        }

        response = await self._make_request("pages.update", **update_data)
        logger.info(f"Deleted page: {page_id}")
        return response

    async def get_page(self, page_id: str) -> Dict[str, Any]:
        """
        Get a specific page.

        Args:
            page_id: Page ID to retrieve

        Returns:
            Page data
        """
        return await self._make_request("pages.retrieve", page_id=page_id)

    async def test_connection(self) -> Dict[str, Any]:
        """
        Test the connection to Notion API.

        Returns:
            Connection test result
        """
        try:
            database_info = await self.get_database_info()
            return {
                "success": True,
                "database_id": self.database_id,
                "database_title": database_info.get("title", [{}])[0].get("plain_text", "Unknown"),
                "message": "接続成功"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "接続失敗"
            }

    def format_datetime(self, dt: datetime) -> str:
        """
        Format datetime for Notion API.

        Args:
            dt: Datetime object

        Returns:
            ISO formatted datetime string
        """
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()

    def parse_datetime(self, dt_str: str) -> datetime:
        """
        Parse datetime from Notion API response.

        Args:
            dt_str: ISO formatted datetime string

        Returns:
            Datetime object
        """
        return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))

    def extract_text_from_rich_text(self, rich_text: List[Dict[str, Any]]) -> str:
        """
        Extract plain text from Notion rich text property.

        Args:
            rich_text: Rich text property

        Returns:
            Plain text string
        """
        if not rich_text or not isinstance(rich_text, list):
            return ""

        return "".join(
            text_obj.get("plain_text", "") for text_obj in rich_text
        )

    def create_rich_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Create rich text property for Notion API.

        Args:
            text: Plain text string

        Returns:
            Rich text property
        """
        if not text:
            return []

        return [
            {
                "type": "text",
                "text": {"content": text}
            }
        ]
