"""
Notion synchronization functionality for SDXL Asset Manager.

This module provides bidirectional synchronization between Notion database
and local SQLite database with data mapping and conflict resolution.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models.database import Model, Run, RunLora, RunTag, Tag
from .notion_client import NotionClient
from .utils.db_utils import DatabaseManager

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class SyncStats:
    """Statistics for sync operations."""
    total_notion_pages: int = 0
    total_local_runs: int = 0
    created_local: int = 0
    updated_local: int = 0
    created_notion: int = 0
    updated_notion: int = 0
    skipped: int = 0
    conflicts: int = 0
    errors: int = 0


class NotionFieldMapper:
    """
    Maps between Notion properties and local database fields.

    Handles data type conversion and field mapping for bidirectional sync.
    """

    # Notion property name -> Local DB field mapping
    FIELD_MAPPING = {
        'Title': 'title',
        'Prompt': 'prompt',
        'Negative': 'negative',
        'CFG': 'cfg',
        'Steps': 'steps',
        'Sampler': 'sampler',
        'Seed': 'seed',
        'Width': 'width',
        'Height': 'height',
        'Model': 'model_name',
        'LoRAs': 'lora_names',
        'Tags': 'tag_names',
        'Status': 'status',
        'Created': 'created_at',
        'Updated': 'updated_at',
        'Notes': 'notes'
    }

    # Reverse mapping for local -> Notion
    REVERSE_MAPPING = {v: k for k, v in FIELD_MAPPING.items()}

    def __init__(self, notion_client: NotionClient):
        self.notion_client = notion_client

    def notion_to_local(self, notion_page: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert Notion page to local database format.

        Args:
            notion_page: Notion page data

        Returns:
            Local database field data
        """
        local_data = {}
        properties = notion_page.get("properties", {})

        for notion_field, local_field in self.FIELD_MAPPING.items():
            if notion_field not in properties:
                continue

            prop = properties[notion_field]
            prop_type = prop.get("type")

            try:
                if prop_type == "title":
                    local_data[local_field] = self._extract_title(prop)
                elif prop_type == "rich_text":
                    local_data[local_field] = self._extract_rich_text(prop)
                elif prop_type == "number":
                    local_data[local_field] = self._extract_number(prop)
                elif prop_type == "select":
                    local_data[local_field] = self._extract_select(prop)
                elif prop_type == "multi_select":
                    local_data[local_field] = self._extract_multi_select(prop)
                elif prop_type == "created_time":
                    local_data[local_field] = self._extract_datetime(prop)
                elif prop_type == "last_edited_time":
                    local_data[local_field] = self._extract_datetime(prop)
                elif prop_type == "url":
                    local_data[local_field] = self._extract_url(prop)

            except Exception as e:
                logger.warning(f"Failed to convert {notion_field}: {e}")
                continue

        # Add Notion-specific fields
        local_data["notion_id"] = notion_page.get("id")
        local_data["notion_url"] = notion_page.get("url")

        return local_data

    def local_to_notion(self, run: Run) -> Dict[str, Any]:
        """
        Convert local database record to Notion format.

        Args:
            run: Local database Run record

        Returns:
            Notion properties format
        """
        notion_properties = {}

        # Title
        if run.title:
            notion_properties["Title"] = {
                "title": self.notion_client.create_rich_text(run.title)
            }

        # Rich text fields
        for field in ["prompt", "negative", "notes"]:
            value = getattr(run, field, None)
            if value:
                notion_field = self.REVERSE_MAPPING.get(field)
                if notion_field:
                    notion_properties[notion_field] = {
                        "rich_text": self.notion_client.create_rich_text(value)
                    }

        # Number fields
        for field in ["cfg", "steps", "seed", "width", "height"]:
            value = getattr(run, field, None)
            if value is not None:
                notion_field = self.REVERSE_MAPPING.get(field)
                if notion_field:
                    notion_properties[notion_field] = {
                        "number": float(value)
                    }

        # Select fields
        for field in ["sampler", "status"]:
            value = getattr(run, field, None)
            if value:
                notion_field = self.REVERSE_MAPPING.get(field)
                if notion_field:
                    notion_properties[notion_field] = {
                        "select": {"name": value}
                    }

        # Model name (special handling)
        if run.model:
            notion_properties["Model"] = {
                "select": {"name": run.model.name}
            }

        # LoRAs (multi-select)
        if run.loras:
            lora_names = [lora.lora_model.name for lora in run.loras]
            notion_properties["LoRAs"] = {
                "multi_select": [{"name": name} for name in lora_names]
            }

        # Tags (multi-select)
        if run.tags:
            tag_names = [tag.tag.name for tag in run.tags]
            notion_properties["Tags"] = {
                "multi_select": [{"name": name} for name in tag_names]
            }


        return notion_properties

    def _extract_title(self, prop: Dict[str, Any]) -> str:
        """Extract title from Notion property."""
        title_data = prop.get("title", [])
        return self.notion_client.extract_text_from_rich_text(title_data)

    def _extract_rich_text(self, prop: Dict[str, Any]) -> str:
        """Extract rich text from Notion property."""
        rich_text_data = prop.get("rich_text", [])
        return self.notion_client.extract_text_from_rich_text(rich_text_data)

    def _extract_number(self, prop: Dict[str, Any]) -> Optional[float]:
        """Extract number from Notion property."""
        return prop.get("number")

    def _extract_select(self, prop: Dict[str, Any]) -> Optional[str]:
        """Extract select value from Notion property."""
        select_data = prop.get("select")
        return select_data.get("name") if select_data else None

    def _extract_multi_select(self, prop: Dict[str, Any]) -> List[str]:
        """Extract multi-select values from Notion property."""
        multi_select_data = prop.get("multi_select", [])
        return [item.get("name", "") for item in multi_select_data]

    def _extract_datetime(self, prop: Dict[str, Any]) -> Optional[datetime]:
        """Extract datetime from Notion property."""
        dt_str = prop.get("created_time") or prop.get("last_edited_time")
        if dt_str:
            return self.notion_client.parse_datetime(dt_str)
        return None

    def _extract_url(self, prop: Dict[str, Any]) -> Optional[str]:
        """Extract URL from Notion property."""
        return prop.get("url")


class NotionSyncManager:
    """
    Manages bidirectional synchronization between Notion and local database.

    Features:
    - One-way sync (Notion → Local, Local → Notion)
    - Bidirectional sync with conflict resolution
    - Dry-run mode for safe preview
    - Detailed statistics and reporting
    """

    def __init__(self, notion_client: NotionClient, dry_run: bool = False):
        """
        Initialize sync manager.

        Args:
            notion_client: Notion API client
            dry_run: If True, no actual changes will be made
        """
        self.notion_client = notion_client
        self.dry_run = dry_run
        self.field_mapper = NotionFieldMapper(notion_client)
        self.stats = SyncStats()
        self.db_manager = DatabaseManager()

        logger.info(f"Notion sync manager initialized (dry_run: {dry_run})")

    async def sync_from_notion(self) -> SyncStats:
        """
        Sync from Notion to local database.

        Returns:
            Sync statistics
        """
        logger.info("Starting Notion → Local sync")
        self.stats = SyncStats()

        try:
            # Get all pages from Notion
            notion_pages = await self.notion_client.get_all_pages()
            self.stats.total_notion_pages = len(notion_pages)

            # Process each page
            with self.db_manager.get_session() as session:
                for page in notion_pages:
                    try:
                        await self._sync_page_to_local(page, session)
                    except Exception as e:
                        logger.error(f"Failed to sync page {page.get('id')}: {e}")
                        self.stats.errors += 1

                if not self.dry_run:
                    session.commit()
                    logger.info("Local database updated")
                else:
                    logger.info("Dry run: no changes made to local database")

        except Exception as e:
            logger.error(f"Sync from Notion failed: {e}")
            self.stats.errors += 1

        self._log_sync_stats("Notion → Local")
        return self.stats

    async def sync_to_notion(self) -> SyncStats:
        """
        Sync from local database to Notion.

        Returns:
            Sync statistics
        """
        logger.info("Starting Local → Notion sync")
        self.stats = SyncStats()

        try:
            with self.db_manager.get_session() as session:
                # Get all local runs
                runs = session.execute(select(Run)).scalars().all()
                self.stats.total_local_runs = len(runs)

                # Get existing Notion pages for comparison
                notion_pages = await self.notion_client.get_all_pages()
                notion_pages_by_id = {
                    page.get("id"): page for page in notion_pages
                    if page.get("id") is not None
                }

                # Process each run
                for run in runs:
                    try:
                        await self._sync_run_to_notion(run, notion_pages_by_id)
                    except Exception as e:
                        logger.error(f"Failed to sync run {run.run_id}: {e}")
                        self.stats.errors += 1

        except Exception as e:
            logger.error(f"Sync to Notion failed: {e}")
            self.stats.errors += 1

        self._log_sync_stats("Local → Notion")
        return self.stats

    async def sync_bidirectional(self) -> SyncStats:
        """
        Perform bidirectional sync with conflict resolution.

        Returns:
            Sync statistics
        """
        logger.info("Starting bidirectional sync")
        self.stats = SyncStats()

        try:
            # Get data from both sources
            notion_pages = await self.notion_client.get_all_pages()

            with self.db_manager.get_session() as session:
                runs = session.execute(select(Run)).scalars().all()

                # Create lookup maps
                notion_pages_by_id = {
                    page.get("id"): page for page in notion_pages
                    if page.get("id") is not None
                }
                runs_by_notion_id = {
                    run.notion_id: run for run in runs if run.notion_id
                }

                self.stats.total_notion_pages = len(notion_pages)
                self.stats.total_local_runs = len(runs)

                # Sync Notion pages that exist locally
                for page in notion_pages:
                    page_id = page.get("id")
                    if page_id in runs_by_notion_id:
                        # Both exist - check for conflicts
                        await self._sync_with_conflict_resolution(
                            page, runs_by_notion_id[page_id], session
                        )
                    else:
                        # Only in Notion - create locally
                        await self._sync_page_to_local(page, session)

                # Sync local runs that don't exist in Notion
                for run in runs:
                    if not run.notion_id or run.notion_id not in notion_pages_by_id:
                        await self._sync_run_to_notion(run, notion_pages_by_id)

                if not self.dry_run:
                    session.commit()
                    logger.info("Bidirectional sync completed")
                else:
                    logger.info("Dry run: no changes made")

        except Exception as e:
            logger.error(f"Bidirectional sync failed: {e}")
            self.stats.errors += 1

        self._log_sync_stats("Bidirectional")
        return self.stats

    async def _sync_page_to_local(self, page: Dict[str, Any], session: Session) -> None:
        """Sync a single Notion page to local database."""
        try:
            # Convert Notion page to local format
            local_data = self.field_mapper.notion_to_local(page)

            # Check if run already exists by notion_id
            notion_id = local_data.get("notion_id")
            existing_run = None

            if notion_id:
                existing_run = session.execute(
                    select(Run).where(Run.notion_id == notion_id)
                ).scalar_one_or_none()

            if existing_run:
                # Update existing run
                await self._update_local_run(existing_run, local_data, session)
                self.stats.updated_local += 1
            else:
                # Create new run
                await self._create_local_run(local_data, session)
                self.stats.created_local += 1

        except Exception as e:
            logger.error(f"Failed to sync page to local: {e}")
            raise

    async def _sync_run_to_notion(
        self,
        run: Run,
        notion_pages_by_id: Dict[str, Dict[str, Any]]
    ) -> None:
        """Sync a single local run to Notion."""
        try:
            # Convert local run to Notion format
            notion_properties = self.field_mapper.local_to_notion(run)

            if run.notion_id and run.notion_id in notion_pages_by_id:
                # Update existing Notion page
                if not self.dry_run:
                    await self.notion_client.update_page(run.notion_id, notion_properties)
                self.stats.updated_notion += 1
            else:
                # Create new Notion page
                if not self.dry_run:
                    response = await self.notion_client.create_page(notion_properties)
                    # Update local run with Notion ID
                    with self.db_manager.get_session() as session:
                        local_run = session.get(Run, run.run_id)
                        if local_run:
                            local_run.notion_id = response.get("id")
                            local_run.notion_url = response.get("url")
                            session.commit()
                self.stats.created_notion += 1

        except Exception as e:
            logger.error(f"Failed to sync run to Notion: {e}")
            raise

    async def _sync_with_conflict_resolution(
        self,
        page: Dict[str, Any],
        run: Run,
        session: Session
    ) -> None:
        """Handle sync with conflict resolution."""
        try:
            # Convert Notion page to local format
            local_data = self.field_mapper.notion_to_local(page)

            # Check for conflicts (last modified time)
            notion_modified = local_data.get("updated_at")
            local_modified = run.updated_at

            if notion_modified and local_modified:
                # Compare modification times
                if notion_modified > local_modified:
                    # Notion is newer - update local
                    await self._update_local_run(run, local_data, session)
                    self.stats.updated_local += 1
                elif local_modified > notion_modified:
                    # Local is newer - update Notion
                    notion_properties = self.field_mapper.local_to_notion(run)
                    if not self.dry_run and run.notion_id:
                        await self.notion_client.update_page(run.notion_id, notion_properties)
                    self.stats.updated_notion += 1
                else:
                    # Same modification time - skip
                    self.stats.skipped += 1
            else:
                # Can't determine conflict - count as conflict
                self.stats.conflicts += 1
                logger.warning(f"Conflict detected for run {run.run_id} / page {page.get('id')}")

        except Exception as e:
            logger.error(f"Failed to resolve conflict: {e}")
            raise

    async def _create_local_run(self, local_data: Dict[str, Any], session: Session) -> None:
        """Create a new local run from Notion data."""
        if self.dry_run:
            return

        try:
            # Create or get model
            model_name = local_data.get("model_name")
            model = await self._get_or_create_model(model_name, session) if model_name else None

            # Create run
            run = Run(
                title=local_data.get("title", ""),
                prompt=local_data.get("prompt", ""),
                negative=local_data.get("negative", ""),
                cfg=local_data.get("cfg"),
                steps=local_data.get("steps"),
                sampler=local_data.get("sampler"),
                seed=local_data.get("seed"),
                width=local_data.get("width"),
                height=local_data.get("height"),
                model=model,
                status=local_data.get("status", "pending"),
                notes=local_data.get("notes"),
                notion_id=local_data.get("notion_id"),
                notion_url=local_data.get("notion_url"),
                created_at=local_data.get("created_at") or datetime.now(timezone.utc),
                updated_at=local_data.get("updated_at") or datetime.now(timezone.utc)
            )

            session.add(run)

            # Handle LoRAs
            lora_names = local_data.get("lora_names", [])
            for lora_name in lora_names:
                lora_model = await self._get_or_create_lora(lora_name, session)
                run_lora = RunLora(run=run, lora_model=lora_model, weight=1.0)
                run.loras.append(run_lora)

            # Handle Tags
            tag_names = local_data.get("tag_names", [])
            for tag_name in tag_names:
                tag = await self._get_or_create_tag(tag_name, session)
                run_tag = RunTag(run=run, tag=tag)
                run.tags.append(run_tag)

            logger.debug(f"Created local run: {run.title}")

        except Exception as e:
            logger.error(f"Failed to create local run: {e}")
            raise

    async def _update_local_run(
        self,
        run: Run,
        local_data: Dict[str, Any],
        session: Session
    ) -> None:
        """Update an existing local run with Notion data."""
        if self.dry_run:
            return

        try:
            # Update basic fields
            for field in ["title", "prompt", "negative", "cfg", "steps",
                         "sampler", "seed", "width", "height", "status",
                         "notes", "notion_url"]:
                if field in local_data:
                    setattr(run, field, local_data[field])

            # Update model
            if "model_name" in local_data:
                model_name = local_data["model_name"]
                if model_name:
                    model = await self._get_or_create_model(model_name, session)
                    run.model = model

            # Update timestamps
            if "updated_at" in local_data:
                run.updated_at = local_data["updated_at"]

            # Update LoRAs
            if "lora_names" in local_data:
                run.loras.clear()
                for lora_name in local_data["lora_names"]:
                    lora_model = await self._get_or_create_lora(lora_name, session)
                    run_lora = RunLora(run=run, lora_model=lora_model, weight=1.0)
                    run.loras.append(run_lora)

            # Update Tags
            if "tag_names" in local_data:
                run.tags.clear()
                for tag_name in local_data["tag_names"]:
                    tag = await self._get_or_create_tag(tag_name, session)
                    run_tag = RunTag(run=run, tag=tag)
                    run.tags.append(run_tag)

            logger.debug(f"Updated local run: {run.title}")

        except Exception as e:
            logger.error(f"Failed to update local run: {e}")
            raise

    async def _get_or_create_model(self, model_name: Optional[str], session: Session) -> Optional[Model]:
        """Get or create a model by name."""
        if not model_name:
            return None

        model = session.execute(
            select(Model).where(Model.name == model_name)
        ).scalar_one_or_none()

        if not model:
            model = Model(name=model_name)
            session.add(model)
            logger.debug(f"Created model: {model_name}")

        return model

    async def _get_or_create_lora(self, lora_name: str, session: Session) -> Model:
        """Get or create a LoRA model by name."""
        lora = session.execute(
            select(Model).where(Model.name == lora_name).where(Model.type == "lora")
        ).scalar_one_or_none()

        if not lora:
            lora = Model(name=lora_name, type="lora")
            session.add(lora)
            logger.debug(f"Created LoRA: {lora_name}")

        return lora

    async def _get_or_create_tag(self, tag_name: str, session: Session) -> Tag:
        """Get or create a tag by name."""
        tag = session.execute(
            select(Tag).where(Tag.name == tag_name)
        ).scalar_one_or_none()

        if not tag:
            tag = Tag(name=tag_name)
            session.add(tag)
            logger.debug(f"Created tag: {tag_name}")

        return tag

    def _log_sync_stats(self, sync_type: str) -> None:
        """Log sync statistics."""
        logger.info(f"=== {sync_type} Sync Statistics ===")
        logger.info(f"Total Notion pages: {self.stats.total_notion_pages}")
        logger.info(f"Total local runs: {self.stats.total_local_runs}")
        logger.info(f"Created locally: {self.stats.created_local}")
        logger.info(f"Updated locally: {self.stats.updated_local}")
        logger.info(f"Created in Notion: {self.stats.created_notion}")
        logger.info(f"Updated in Notion: {self.stats.updated_notion}")
        logger.info(f"Skipped: {self.stats.skipped}")
        logger.info(f"Conflicts: {self.stats.conflicts}")
        logger.info(f"Errors: {self.stats.errors}")

    async def detect_conflicts(self) -> List[Dict[str, Any]]:
        """
        Detect conflicts between Notion and local data.

        Returns:
            List of conflicts
        """
        conflicts = []

        try:
            # Get data from both sources
            notion_pages = await self.notion_client.get_all_pages()

            with self.db_manager.get_session() as session:
                runs = session.execute(select(Run)).scalars().all()

                # Create lookup maps
                runs_by_notion_id = {
                    run.notion_id: run for run in runs if run.notion_id
                }

                # Check for conflicts
                for page in notion_pages:
                    page_id = page.get("id")
                    if page_id in runs_by_notion_id:
                        run = runs_by_notion_id[page_id]

                        # Convert Notion page to local format
                        local_data = self.field_mapper.notion_to_local(page)

                        # Check for conflicts
                        notion_modified = local_data.get("updated_at")
                        local_modified = run.updated_at

                        if notion_modified and local_modified and notion_modified != local_modified:
                            conflicts.append({
                                "run_id": run.run_id,
                                "notion_id": page_id,
                                "notion_title": local_data.get("title", ""),
                                "local_title": run.title,
                                "notion_modified": notion_modified,
                                "local_modified": local_modified,
                                "conflict_type": "modification_time"
                            })

        except Exception as e:
            logger.error(f"Failed to detect conflicts: {e}")

        return conflicts
