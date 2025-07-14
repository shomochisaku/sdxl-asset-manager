"""Tests for Notion API client."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from src.notion_client import (
    NotionClient,
    NotionRateLimiter,
    NotionAPIError,
    NotionAuthenticationError,
    NotionPermissionError,
    NotionRateLimitError,
    NotionTimeoutError,
    NotionConnectionError,
)


class TestNotionRateLimiter:
    """Test rate limiter functionality."""

    @pytest.mark.asyncio
    async def test_rate_limiter_allows_requests_within_limit(self):
        """Test that rate limiter allows requests within limit."""
        limiter = NotionRateLimiter(max_requests=3, time_window=1.0)
        
        # Should allow 3 requests without waiting
        await limiter.wait_if_needed()
        await limiter.wait_if_needed()
        await limiter.wait_if_needed()
        
        # Should have 3 requests recorded
        assert len(limiter.requests) == 3

    @pytest.mark.asyncio
    async def test_rate_limiter_waits_when_limit_exceeded(self):
        """Test that rate limiter waits when limit is exceeded."""
        limiter = NotionRateLimiter(max_requests=2, time_window=1.0)
        
        # Fill up the rate limit
        await limiter.wait_if_needed()
        await limiter.wait_if_needed()
        
        # This should cause a wait
        start_time = asyncio.get_event_loop().time()
        await limiter.wait_if_needed()
        end_time = asyncio.get_event_loop().time()
        
        # Should have waited some time
        assert end_time > start_time

    @pytest.mark.asyncio
    async def test_rate_limiter_clears_old_requests(self):
        """Test that rate limiter clears old requests."""
        limiter = NotionRateLimiter(max_requests=2, time_window=0.1)
        
        # Make requests
        await limiter.wait_if_needed()
        await limiter.wait_if_needed()
        
        # Wait for time window to expire
        await asyncio.sleep(0.2)
        
        # Should allow new requests
        await limiter.wait_if_needed()
        assert len(limiter.requests) == 1


class TestNotionClient:
    """Test Notion client functionality."""

    @pytest.fixture
    def mock_notion_client(self):
        """Create a mock Notion client."""
        with patch('src.notion_client.Client') as mock_client:
            yield mock_client

    @pytest.fixture
    def notion_client(self, mock_notion_client):
        """Create a NotionClient instance."""
        return NotionClient(
            api_key="test_key",
            database_id="test_db_id",
            max_retries=1,
            timeout=10
        )

    def test_notion_client_initialization(self, notion_client):
        """Test Notion client initialization."""
        assert notion_client.api_key == "test_key"
        assert notion_client.database_id == "test_db_id"
        assert notion_client.max_retries == 1
        assert notion_client.timeout == 10
        assert notion_client.client is not None
        assert notion_client.rate_limiter is not None

    @pytest.mark.asyncio
    async def test_get_database_info_success(self, notion_client):
        """Test successful database info retrieval."""
        mock_response = {"id": "test_db_id", "title": [{"plain_text": "Test DB"}]}
        notion_client.client.databases.retrieve = MagicMock(return_value=mock_response)
        
        result = await notion_client.get_database_info()
        
        assert result == mock_response
        notion_client.client.databases.retrieve.assert_called_once_with(database_id="test_db_id")

    @pytest.mark.asyncio
    async def test_get_database_pages_success(self, notion_client):
        """Test successful database pages retrieval."""
        mock_response = {
            "results": [{"id": "page1"}, {"id": "page2"}],
            "has_more": False
        }
        notion_client.client.databases.query = MagicMock(return_value=mock_response)
        
        result = await notion_client.get_database_pages()
        
        assert result == mock_response
        notion_client.client.databases.query.assert_called_once_with(
            database_id="test_db_id",
            page_size=100
        )

    @pytest.mark.asyncio
    async def test_get_database_pages_with_cursor(self, notion_client):
        """Test database pages retrieval with cursor."""
        mock_response = {
            "results": [{"id": "page1"}],
            "has_more": False
        }
        notion_client.client.databases.query = MagicMock(return_value=mock_response)
        
        result = await notion_client.get_database_pages(start_cursor="cursor123")
        
        assert result == mock_response
        notion_client.client.databases.query.assert_called_once_with(
            database_id="test_db_id",
            page_size=100,
            start_cursor="cursor123"
        )

    @pytest.mark.asyncio
    async def test_get_all_pages_single_request(self, notion_client):
        """Test get all pages with single request."""
        mock_response = {
            "results": [{"id": "page1"}, {"id": "page2"}],
            "has_more": False
        }
        notion_client.client.databases.query = MagicMock(return_value=mock_response)
        
        result = await notion_client.get_all_pages()
        
        assert len(result) == 2
        assert result[0]["id"] == "page1"
        assert result[1]["id"] == "page2"

    @pytest.mark.asyncio
    async def test_get_all_pages_multiple_requests(self, notion_client):
        """Test get all pages with multiple requests."""
        mock_responses = [
            {
                "results": [{"id": "page1"}],
                "has_more": True,
                "next_cursor": "cursor1"
            },
            {
                "results": [{"id": "page2"}],
                "has_more": False
            }
        ]
        notion_client.client.databases.query = MagicMock(side_effect=mock_responses)
        
        result = await notion_client.get_all_pages()
        
        assert len(result) == 2
        assert result[0]["id"] == "page1"
        assert result[1]["id"] == "page2"
        assert notion_client.client.databases.query.call_count == 2

    @pytest.mark.asyncio
    async def test_create_page_success(self, notion_client):
        """Test successful page creation."""
        properties = {"Title": {"title": [{"text": {"content": "Test"}}]}}
        mock_response = {"id": "new_page_id", "url": "https://notion.so/new_page"}
        notion_client.client.pages.create = MagicMock(return_value=mock_response)
        
        result = await notion_client.create_page(properties)
        
        assert result == mock_response
        notion_client.client.pages.create.assert_called_once_with(
            parent={"database_id": "test_db_id"},
            properties=properties
        )

    @pytest.mark.asyncio
    async def test_update_page_success(self, notion_client):
        """Test successful page update."""
        properties = {"Title": {"title": [{"text": {"content": "Updated"}}]}}
        mock_response = {"id": "page_id", "url": "https://notion.so/page"}
        notion_client.client.pages.update = MagicMock(return_value=mock_response)
        
        result = await notion_client.update_page("page_id", properties)
        
        assert result == mock_response
        notion_client.client.pages.update.assert_called_once_with(
            page_id="page_id",
            properties=properties
        )

    @pytest.mark.asyncio
    async def test_delete_page_success(self, notion_client):
        """Test successful page deletion."""
        mock_response = {"id": "page_id", "archived": True}
        notion_client.client.pages.update = MagicMock(return_value=mock_response)
        
        result = await notion_client.delete_page("page_id")
        
        assert result == mock_response
        notion_client.client.pages.update.assert_called_once_with(
            page_id="page_id",
            archived=True
        )

    @pytest.mark.asyncio
    async def test_get_page_success(self, notion_client):
        """Test successful page retrieval."""
        mock_response = {"id": "page_id", "properties": {}}
        notion_client.client.pages.retrieve = MagicMock(return_value=mock_response)
        
        result = await notion_client.get_page("page_id")
        
        assert result == mock_response
        notion_client.client.pages.retrieve.assert_called_once_with(page_id="page_id")

    @pytest.mark.asyncio
    async def test_test_connection_success(self, notion_client):
        """Test successful connection test."""
        mock_db_info = {
            "id": "test_db_id",
            "title": [{"plain_text": "Test Database"}]
        }
        notion_client.client.databases.retrieve = MagicMock(return_value=mock_db_info)
        
        result = await notion_client.test_connection()
        
        assert result["success"] is True
        assert result["database_id"] == "test_db_id"
        assert result["database_title"] == "Test Database"
        assert result["message"] == "接続成功"

    @pytest.mark.asyncio
    async def test_test_connection_failure(self, notion_client):
        """Test failed connection test."""
        notion_client.client.databases.retrieve = MagicMock(
            side_effect=Exception("Connection failed")
        )
        
        result = await notion_client.test_connection()
        
        assert result["success"] is False
        assert "Connection failed" in result["error"]
        assert result["message"] == "接続失敗"

    @pytest.mark.asyncio
    async def test_authentication_error_handling(self, notion_client):
        """Test authentication error handling."""
        from notion_client.errors import HTTPResponseError
        
        mock_error = HTTPResponseError(
            response=MagicMock(status_code=401),
            message="Unauthorized"
        )
        mock_error.status = 401
        notion_client.client.databases.retrieve = MagicMock(side_effect=mock_error)
        
        with pytest.raises(NotionAuthenticationError):
            await notion_client.get_database_info()

    @pytest.mark.asyncio
    async def test_permission_error_handling(self, notion_client):
        """Test permission error handling."""
        from notion_client.errors import HTTPResponseError
        
        mock_error = HTTPResponseError(
            response=MagicMock(status_code=403),
            message="Forbidden"
        )
        mock_error.status = 403
        notion_client.client.databases.retrieve = MagicMock(side_effect=mock_error)
        
        with pytest.raises(NotionPermissionError):
            await notion_client.get_database_info()

    @pytest.mark.asyncio
    async def test_rate_limit_error_handling(self, notion_client):
        """Test rate limit error handling."""
        from notion_client.errors import HTTPResponseError
        
        mock_error = HTTPResponseError(
            response=MagicMock(status_code=429),
            message="Rate limited"
        )
        mock_error.status = 429
        notion_client.client.databases.retrieve = MagicMock(side_effect=mock_error)
        
        with pytest.raises(NotionRateLimitError):
            await notion_client.get_database_info()

    @pytest.mark.asyncio
    async def test_timeout_error_handling(self, notion_client):
        """Test timeout error handling."""
        from notion_client.errors import RequestTimeoutError
        
        notion_client.client.databases.retrieve = MagicMock(
            side_effect=RequestTimeoutError("Timeout")
        )
        
        with pytest.raises(NotionTimeoutError):
            await notion_client.get_database_info()

    @pytest.mark.asyncio
    async def test_connection_error_handling(self, notion_client):
        """Test connection error handling."""
        from notion_client.errors import HTTPResponseError
        
        mock_error = HTTPResponseError(
            response=MagicMock(status_code=500),
            message="Server error"
        )
        mock_error.status = 500
        notion_client.client.databases.retrieve = MagicMock(side_effect=mock_error)
        
        with pytest.raises(NotionConnectionError):
            await notion_client.get_database_info()

    @pytest.mark.asyncio
    async def test_retry_logic(self, notion_client):
        """Test retry logic on transient errors."""
        from notion_client.errors import HTTPResponseError
        
        # First call fails, second succeeds
        mock_response = {"id": "test_db_id"}
        mock_error = HTTPResponseError(
            response=MagicMock(status_code=500),
            message="Temporary failure"
        )
        mock_error.status = 500
        
        notion_client.client.databases.retrieve = MagicMock(
            side_effect=[mock_error, mock_response]
        )
        
        result = await notion_client.get_database_info()
        
        assert result == mock_response
        assert notion_client.client.databases.retrieve.call_count == 2

    def test_format_datetime(self, notion_client):
        """Test datetime formatting."""
        dt = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        formatted = notion_client.format_datetime(dt)
        
        assert formatted == "2023-01-01T12:00:00+00:00"

    def test_format_datetime_without_timezone(self, notion_client):
        """Test datetime formatting without timezone."""
        dt = datetime(2023, 1, 1, 12, 0, 0)
        formatted = notion_client.format_datetime(dt)
        
        assert formatted == "2023-01-01T12:00:00+00:00"

    def test_parse_datetime(self, notion_client):
        """Test datetime parsing."""
        dt_str = "2023-01-01T12:00:00.000Z"
        parsed = notion_client.parse_datetime(dt_str)
        
        assert parsed.year == 2023
        assert parsed.month == 1
        assert parsed.day == 1
        assert parsed.hour == 12
        assert parsed.minute == 0
        assert parsed.second == 0

    def test_extract_text_from_rich_text(self, notion_client):
        """Test rich text extraction."""
        rich_text = [
            {"plain_text": "Hello "},
            {"plain_text": "World"}
        ]
        
        result = notion_client.extract_text_from_rich_text(rich_text)
        
        assert result == "Hello World"

    def test_extract_text_from_empty_rich_text(self, notion_client):
        """Test rich text extraction from empty list."""
        result = notion_client.extract_text_from_rich_text([])
        assert result == ""
        
        result = notion_client.extract_text_from_rich_text(None)
        assert result == ""

    def test_create_rich_text(self, notion_client):
        """Test rich text creation."""
        result = notion_client.create_rich_text("Hello World")
        
        expected = [
            {
                "type": "text",
                "text": {"content": "Hello World"}
            }
        ]
        
        assert result == expected

    def test_create_rich_text_empty(self, notion_client):
        """Test rich text creation with empty string."""
        result = notion_client.create_rich_text("")
        assert result == []
        
        result = notion_client.create_rich_text(None)
        assert result == []