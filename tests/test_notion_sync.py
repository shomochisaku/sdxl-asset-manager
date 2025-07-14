"""Tests for Notion sync functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from src.notion_sync import (
    NotionFieldMapper,
    NotionSyncManager,
    SyncStats,
)
from src.notion_client import NotionClient
from src.models.database import Model, Tag, Run, RunLora, RunTag


class TestSyncStats:
    """Test sync statistics data class."""

    def test_sync_stats_initialization(self):
        """Test sync stats initialization."""
        stats = SyncStats()
        
        assert stats.total_notion_pages == 0
        assert stats.total_local_runs == 0
        assert stats.created_local == 0
        assert stats.updated_local == 0
        assert stats.created_notion == 0
        assert stats.updated_notion == 0
        assert stats.skipped == 0
        assert stats.conflicts == 0
        assert stats.errors == 0


class TestNotionFieldMapper:
    """Test field mapping functionality."""

    @pytest.fixture
    def mock_notion_client(self):
        """Create a mock Notion client."""
        client = MagicMock()
        client.extract_text_from_rich_text = MagicMock()
        client.create_rich_text = MagicMock()
        client.parse_datetime = MagicMock()
        return client

    @pytest.fixture
    def field_mapper(self, mock_notion_client):
        """Create a field mapper instance."""
        return NotionFieldMapper(mock_notion_client)

    def test_field_mapping_constants(self, field_mapper):
        """Test field mapping constants."""
        assert field_mapper.FIELD_MAPPING['Title'] == 'title'
        assert field_mapper.FIELD_MAPPING['Prompt'] == 'prompt'
        assert field_mapper.FIELD_MAPPING['Negative'] == 'negative'
        assert field_mapper.FIELD_MAPPING['CFG'] == 'cfg'
        assert field_mapper.FIELD_MAPPING['Steps'] == 'steps'
        
        # Test reverse mapping
        assert field_mapper.REVERSE_MAPPING['title'] == 'Title'
        assert field_mapper.REVERSE_MAPPING['prompt'] == 'Prompt'

    def test_notion_to_local_title_field(self, field_mapper):
        """Test Notion to local conversion for title field."""
        notion_page = {
            "id": "page_id",
            "url": "https://notion.so/page",
            "properties": {
                "Title": {
                    "type": "title",
                    "title": [{"plain_text": "Test Title"}]
                }
            }
        }
        
        field_mapper.notion_client.extract_text_from_rich_text.return_value = "Test Title"
        
        result = field_mapper.notion_to_local(notion_page)
        
        assert result["title"] == "Test Title"
        assert result["notion_id"] == "page_id"
        assert result["notion_url"] == "https://notion.so/page"

    def test_notion_to_local_rich_text_field(self, field_mapper):
        """Test Notion to local conversion for rich text field."""
        notion_page = {
            "id": "page_id",
            "properties": {
                "Prompt": {
                    "type": "rich_text",
                    "rich_text": [{"plain_text": "Test prompt"}]
                }
            }
        }
        
        field_mapper.notion_client.extract_text_from_rich_text.return_value = "Test prompt"
        
        result = field_mapper.notion_to_local(notion_page)
        
        assert result["prompt"] == "Test prompt"

    def test_notion_to_local_number_field(self, field_mapper):
        """Test Notion to local conversion for number field."""
        notion_page = {
            "id": "page_id",
            "properties": {
                "CFG": {
                    "type": "number",
                    "number": 7.5
                }
            }
        }
        
        result = field_mapper.notion_to_local(notion_page)
        
        assert result["cfg"] == 7.5

    def test_notion_to_local_select_field(self, field_mapper):
        """Test Notion to local conversion for select field."""
        notion_page = {
            "id": "page_id",
            "properties": {
                "Sampler": {
                    "type": "select",
                    "select": {"name": "DPM++ 2M"}
                }
            }
        }
        
        result = field_mapper.notion_to_local(notion_page)
        
        assert result["sampler"] == "DPM++ 2M"

    def test_notion_to_local_multi_select_field(self, field_mapper):
        """Test Notion to local conversion for multi-select field."""
        notion_page = {
            "id": "page_id",
            "properties": {
                "Tags": {
                    "type": "multi_select",
                    "multi_select": [
                        {"name": "anime"},
                        {"name": "portrait"}
                    ]
                }
            }
        }
        
        result = field_mapper.notion_to_local(notion_page)
        
        assert result["tag_names"] == ["anime", "portrait"]

    def test_notion_to_local_datetime_field(self, field_mapper):
        """Test Notion to local conversion for datetime field."""
        test_datetime = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        notion_page = {
            "id": "page_id",
            "properties": {
                "Created": {
                    "type": "created_time",
                    "created_time": "2023-01-01T12:00:00.000Z"
                }
            }
        }
        
        field_mapper.notion_client.parse_datetime.return_value = test_datetime
        
        result = field_mapper.notion_to_local(notion_page)
        
        assert result["created_at"] == test_datetime

    def test_local_to_notion_basic_fields(self, field_mapper):
        """Test local to Notion conversion for basic fields."""
        # Create a mock run
        run = MagicMock()
        run.title = "Test Title"
        run.prompt = "Test prompt"
        run.negative = "Test negative"
        run.cfg = 7.5
        run.steps = 20
        run.sampler = "DPM++ 2M"
        run.seed = 12345
        run.model = None
        run.loras = []
        run.tags = []
        
        field_mapper.notion_client.create_rich_text.return_value = [
            {"type": "text", "text": {"content": "Test"}}
        ]
        
        result = field_mapper.local_to_notion(run)
        
        assert "Title" in result
        assert "Prompt" in result
        assert "Negative" in result
        assert result["CFG"]["number"] == 7.5
        assert result["Steps"]["number"] == 20
        assert result["Sampler"]["select"]["name"] == "DPM++ 2M"
        assert result["Seed"]["number"] == 12345

    def test_local_to_notion_with_model(self, field_mapper):
        """Test local to Notion conversion with model."""
        # Create a mock run with model
        run = MagicMock()
        run.title = "Test Title"
        run.model = MagicMock()
        run.model.name = "TestModel"
        run.loras = []
        run.tags = []
        
        field_mapper.notion_client.create_rich_text.return_value = [
            {"type": "text", "text": {"content": "Test Title"}}
        ]
        
        result = field_mapper.local_to_notion(run)
        
        assert result["Model"]["select"]["name"] == "TestModel"

    def test_local_to_notion_with_loras(self, field_mapper):
        """Test local to Notion conversion with LoRAs."""
        # Create a mock run with LoRAs
        run = MagicMock()
        run.title = "Test Title"
        run.model = None
        run.tags = []
        
        # Mock LoRA relationships
        lora1 = MagicMock()
        lora1.lora_model.name = "LoRA1"
        lora2 = MagicMock()
        lora2.lora_model.name = "LoRA2"
        run.loras = [lora1, lora2]
        
        field_mapper.notion_client.create_rich_text.return_value = [
            {"type": "text", "text": {"content": "Test Title"}}
        ]
        
        result = field_mapper.local_to_notion(run)
        
        assert "LoRAs" in result
        assert len(result["LoRAs"]["multi_select"]) == 2
        assert result["LoRAs"]["multi_select"][0]["name"] == "LoRA1"
        assert result["LoRAs"]["multi_select"][1]["name"] == "LoRA2"

    def test_local_to_notion_with_tags(self, field_mapper):
        """Test local to Notion conversion with tags."""
        # Create a mock run with tags
        run = MagicMock()
        run.title = "Test Title"
        run.model = None
        run.loras = []
        
        # Mock tag relationships
        tag1 = MagicMock()
        tag1.tag.name = "anime"
        tag2 = MagicMock()
        tag2.tag.name = "portrait"
        run.tags = [tag1, tag2]
        
        field_mapper.notion_client.create_rich_text.return_value = [
            {"type": "text", "text": {"content": "Test Title"}}
        ]
        
        result = field_mapper.local_to_notion(run)
        
        assert "Tags" in result
        assert len(result["Tags"]["multi_select"]) == 2
        assert result["Tags"]["multi_select"][0]["name"] == "anime"
        assert result["Tags"]["multi_select"][1]["name"] == "portrait"

    def test_extract_methods(self, field_mapper):
        """Test various extract methods."""
        # Test _extract_title
        prop = {"title": [{"plain_text": "Test Title"}]}
        field_mapper.notion_client.extract_text_from_rich_text.return_value = "Test Title"
        result = field_mapper._extract_title(prop)
        assert result == "Test Title"
        
        # Test _extract_rich_text
        prop = {"rich_text": [{"plain_text": "Test Text"}]}
        field_mapper.notion_client.extract_text_from_rich_text.return_value = "Test Text"
        result = field_mapper._extract_rich_text(prop)
        assert result == "Test Text"
        
        # Test _extract_number
        prop = {"number": 42}
        result = field_mapper._extract_number(prop)
        assert result == 42
        
        # Test _extract_select
        prop = {"select": {"name": "Test Value"}}
        result = field_mapper._extract_select(prop)
        assert result == "Test Value"
        
        # Test _extract_multi_select
        prop = {"multi_select": [{"name": "Tag1"}, {"name": "Tag2"}]}
        result = field_mapper._extract_multi_select(prop)
        assert result == ["Tag1", "Tag2"]
        
        # Test _extract_url
        prop = {"url": "https://example.com"}
        result = field_mapper._extract_url(prop)
        assert result == "https://example.com"


class TestNotionSyncManager:
    """Test sync manager functionality."""

    @pytest.fixture
    def mock_notion_client(self):
        """Create a mock Notion client."""
        client = MagicMock()
        client.get_all_pages = AsyncMock()
        client.create_page = AsyncMock()
        client.update_page = AsyncMock()
        return client

    @pytest.fixture
    def mock_db_manager(self):
        """Create a mock database manager."""
        with patch('src.notion_sync.DatabaseManager') as mock_db:
            mock_session = MagicMock()
            mock_db.return_value.get_session.return_value.__enter__.return_value = mock_session
            mock_db.return_value.get_session.return_value.__exit__.return_value = None
            yield mock_db, mock_session

    @pytest.fixture
    def sync_manager(self, mock_notion_client, mock_db_manager):
        """Create a sync manager instance."""
        return NotionSyncManager(mock_notion_client, dry_run=False)

    def test_sync_manager_initialization(self, sync_manager):
        """Test sync manager initialization."""
        assert sync_manager.notion_client is not None
        assert sync_manager.dry_run is False
        assert sync_manager.field_mapper is not None
        assert sync_manager.stats is not None
        assert sync_manager.db_manager is not None

    def test_sync_manager_dry_run_mode(self, mock_notion_client, mock_db_manager):
        """Test sync manager in dry run mode."""
        sync_manager = NotionSyncManager(mock_notion_client, dry_run=True)
        assert sync_manager.dry_run is True

    @pytest.mark.asyncio
    async def test_sync_from_notion_empty_database(self, sync_manager):
        """Test sync from Notion with empty database."""
        sync_manager.notion_client.get_all_pages.return_value = []
        
        result = await sync_manager.sync_from_notion()
        
        assert result.total_notion_pages == 0
        assert result.created_local == 0
        assert result.updated_local == 0
        assert result.errors == 0

    @pytest.mark.asyncio
    async def test_sync_from_notion_with_pages(self, sync_manager):
        """Test sync from Notion with pages."""
        mock_pages = [
            {
                "id": "page1",
                "properties": {
                    "Title": {"type": "title", "title": [{"plain_text": "Page 1"}]}
                }
            },
            {
                "id": "page2",
                "properties": {
                    "Title": {"type": "title", "title": [{"plain_text": "Page 2"}]}
                }
            }
        ]
        
        sync_manager.notion_client.get_all_pages.return_value = mock_pages
        
        with patch.object(sync_manager, '_sync_page_to_local') as mock_sync:
            mock_sync.return_value = None
            
            result = await sync_manager.sync_from_notion()
            
            assert result.total_notion_pages == 2
            assert mock_sync.call_count == 2

    @pytest.mark.asyncio
    async def test_sync_to_notion_empty_database(self, sync_manager):
        """Test sync to Notion with empty local database."""
        with patch.object(sync_manager.db_manager, 'get_session') as mock_session:
            mock_session.return_value.__enter__.return_value.execute.return_value.scalars.return_value.all.return_value = []
            
            result = await sync_manager.sync_to_notion()
            
            assert result.total_local_runs == 0
            assert result.created_notion == 0
            assert result.updated_notion == 0
            assert result.errors == 0

    @pytest.mark.asyncio
    async def test_sync_to_notion_with_runs(self, sync_manager):
        """Test sync to Notion with local runs."""
        mock_runs = [
            MagicMock(run_id=1, title="Run 1", notion_id=None),
            MagicMock(run_id=2, title="Run 2", notion_id="existing_page")
        ]
        
        with patch.object(sync_manager.db_manager, 'get_session') as mock_session:
            mock_session.return_value.__enter__.return_value.execute.return_value.scalars.return_value.all.return_value = mock_runs
            
            sync_manager.notion_client.get_all_pages.return_value = [
                {"id": "existing_page", "properties": {}}
            ]
            
            with patch.object(sync_manager, '_sync_run_to_notion') as mock_sync:
                mock_sync.return_value = None
                
                result = await sync_manager.sync_to_notion()
                
                assert result.total_local_runs == 2
                assert mock_sync.call_count == 2

    @pytest.mark.asyncio
    async def test_sync_bidirectional(self, sync_manager):
        """Test bidirectional sync."""
        mock_pages = [
            {
                "id": "page1",
                "properties": {
                    "Title": {"type": "title", "title": [{"plain_text": "Page 1"}]}
                }
            }
        ]
        
        mock_runs = [
            MagicMock(run_id=1, title="Run 1", notion_id="page1"),
            MagicMock(run_id=2, title="Run 2", notion_id=None)
        ]
        
        sync_manager.notion_client.get_all_pages.return_value = mock_pages
        
        with patch.object(sync_manager.db_manager, 'get_session') as mock_session:
            mock_session.return_value.__enter__.return_value.execute.return_value.scalars.return_value.all.return_value = mock_runs
            
            with patch.object(sync_manager, '_sync_with_conflict_resolution') as mock_conflict:
                with patch.object(sync_manager, '_sync_run_to_notion') as mock_sync_to_notion:
                    mock_conflict.return_value = None
                    mock_sync_to_notion.return_value = None
                    
                    result = await sync_manager.sync_bidirectional()
                    
                    assert result.total_notion_pages == 1
                    assert result.total_local_runs == 2
                    assert mock_conflict.call_count == 1
                    assert mock_sync_to_notion.call_count == 1

    @pytest.mark.asyncio
    async def test_detect_conflicts_no_conflicts(self, sync_manager):
        """Test conflict detection with no conflicts."""
        # Use the same datetime for both local and notion to avoid false conflicts
        fixed_datetime = datetime.now(timezone.utc)
        
        mock_pages = [
            {
                "id": "page1",
                "properties": {
                    "Title": {"type": "title", "title": [{"plain_text": "Page 1"}]}
                }
            }
        ]
        
        mock_runs = [
            MagicMock(run_id=1, title="Run 1", notion_id="page1", updated_at=fixed_datetime)
        ]
        
        sync_manager.notion_client.get_all_pages.return_value = mock_pages
        
        with patch.object(sync_manager.db_manager, 'get_session') as mock_session:
            mock_session.return_value.__enter__.return_value.execute.return_value.scalars.return_value.all.return_value = mock_runs
            
            with patch.object(sync_manager.field_mapper, 'notion_to_local') as mock_convert:
                mock_convert.return_value = {"updated_at": fixed_datetime}
                
                conflicts = await sync_manager.detect_conflicts()
                
                assert len(conflicts) == 0

    @pytest.mark.asyncio
    async def test_detect_conflicts_with_conflicts(self, sync_manager):
        """Test conflict detection with conflicts."""
        mock_pages = [
            {
                "id": "page1",
                "properties": {
                    "Title": {"type": "title", "title": [{"plain_text": "Page 1"}]}
                }
            }
        ]
        
        local_time = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        notion_time = datetime(2023, 1, 1, 13, 0, 0, tzinfo=timezone.utc)
        
        mock_runs = [
            MagicMock(run_id=1, title="Run 1", notion_id="page1", updated_at=local_time)
        ]
        
        sync_manager.notion_client.get_all_pages.return_value = mock_pages
        
        with patch.object(sync_manager.db_manager, 'get_session') as mock_session:
            mock_session.return_value.__enter__.return_value.execute.return_value.scalars.return_value.all.return_value = mock_runs
            
            with patch.object(sync_manager.field_mapper, 'notion_to_local') as mock_convert:
                mock_convert.return_value = {
                    "title": "Page 1",
                    "updated_at": notion_time
                }
                
                conflicts = await sync_manager.detect_conflicts()
                
                assert len(conflicts) == 1
                assert conflicts[0]["run_id"] == 1
                assert conflicts[0]["notion_id"] == "page1"
                assert conflicts[0]["local_modified"] == local_time
                assert conflicts[0]["notion_modified"] == notion_time

    @pytest.mark.asyncio
    async def test_get_or_create_model_existing(self, sync_manager):
        """Test get or create model with existing model."""
        mock_session = MagicMock()
        mock_model = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_model
        
        result = await sync_manager._get_or_create_model("TestModel", mock_session)
        
        assert result == mock_model
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_or_create_model_new(self, sync_manager):
        """Test get or create model with new model."""
        mock_session = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = None
        
        result = await sync_manager._get_or_create_model("TestModel", mock_session)
        
        # Check that a new model was created with the correct name
        assert result.name == "TestModel"
        assert result.type is None  # Default type
        # Check that the model was added to the session
        mock_session.add.assert_called_once()
        added_model = mock_session.add.call_args[0][0]
        assert added_model.name == "TestModel"

    @pytest.mark.asyncio
    async def test_get_or_create_lora_existing(self, sync_manager):
        """Test get or create LoRA with existing LoRA."""
        mock_session = MagicMock()
        mock_lora = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_lora
        
        result = await sync_manager._get_or_create_lora("TestLoRA", mock_session)
        
        assert result == mock_lora
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_or_create_lora_new(self, sync_manager):
        """Test get or create LoRA with new LoRA."""
        mock_session = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = None
        
        result = await sync_manager._get_or_create_lora("TestLoRA", mock_session)
        
        # Check that a new LoRA was created with the correct name and type
        assert result.name == "TestLoRA"
        assert result.type == "lora"
        # Check that the LoRA was added to the session
        mock_session.add.assert_called_once()
        added_lora = mock_session.add.call_args[0][0]
        assert added_lora.name == "TestLoRA"
        assert added_lora.type == "lora"

    @pytest.mark.asyncio
    async def test_get_or_create_tag_existing(self, sync_manager):
        """Test get or create tag with existing tag."""
        mock_session = MagicMock()
        mock_tag = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_tag
        
        result = await sync_manager._get_or_create_tag("TestTag", mock_session)
        
        assert result == mock_tag
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_or_create_tag_new(self, sync_manager):
        """Test get or create tag with new tag."""
        mock_session = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = None
        
        result = await sync_manager._get_or_create_tag("TestTag", mock_session)
        
        # Check that a new tag was created with the correct name
        assert result.name == "TestTag"
        # Check that the tag was added to the session
        mock_session.add.assert_called_once()
        added_tag = mock_session.add.call_args[0][0]
        assert added_tag.name == "TestTag"

    def test_log_sync_stats(self, sync_manager):
        """Test sync statistics logging."""
        sync_manager.stats.total_notion_pages = 5
        sync_manager.stats.total_local_runs = 3
        sync_manager.stats.created_local = 2
        sync_manager.stats.updated_local = 1
        sync_manager.stats.created_notion = 1
        sync_manager.stats.updated_notion = 0
        sync_manager.stats.skipped = 0
        sync_manager.stats.conflicts = 0
        sync_manager.stats.errors = 0
        
        # This should not raise an exception
        sync_manager._log_sync_stats("Test Sync")

    @pytest.mark.asyncio
    async def test_dry_run_mode(self, mock_notion_client, mock_db_manager):
        """Test that dry run mode doesn't make actual changes."""
        sync_manager = NotionSyncManager(mock_notion_client, dry_run=True)
        
        # Mock data
        local_data = {
            "title": "Test Title",
            "prompt": "Test prompt",
            "notion_id": "test_id"
        }
        
        mock_session = MagicMock()
        
        # Test create local run in dry run mode
        await sync_manager._create_local_run(local_data, mock_session)
        
        # Should not add anything to session
        mock_session.add.assert_not_called()
        
        # Test update local run in dry run mode
        mock_run = MagicMock()
        await sync_manager._update_local_run(mock_run, local_data, mock_session)
        
        # Should not modify the run (mocked, so we can't verify exactly)