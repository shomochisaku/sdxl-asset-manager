"""SQLAlchemy models for SDXL Asset Manager.

このモジュールは画像生成ワークフロー管理システムのデータベースモデルを定義します。
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    REAL,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    event,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

if TYPE_CHECKING:
    pass


class Base(DeclarativeBase):
    """SQLAlchemy declarative base class."""
    pass


class Model(Base):
    """モデル情報テーブル.

    Checkpoints, LoRA, VAE, ControlNetなどのAIモデル情報を管理します。
    """

    __tablename__ = "models"

    model_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    type: Mapped[str] = mapped_column(String, default="checkpoint", nullable=False)
    filename: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.current_timestamp(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.current_timestamp(), nullable=False
    )

    # Relationships
    runs: Mapped[List["Run"]] = relationship("Run", back_populates="model")
    lora_runs: Mapped[List["RunLora"]] = relationship(
        "RunLora", foreign_keys="RunLora.lora_id", back_populates="lora_model"
    )

    def __repr__(self) -> str:
        """文字列表現を返します."""
        return f"<Model(id={self.model_id}, name='{self.name}', type='{self.type}')>"


class Run(Base):
    """実行履歴テーブル.
    
    画像生成の実行履歴とパラメータを管理します。
    """

    __tablename__ = "runs"

    run_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("models.model_id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    negative: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cfg: Mapped[float] = mapped_column(REAL, default=7.0, nullable=False)
    steps: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    sampler: Mapped[str] = mapped_column(String, default="DPM++ 2M", nullable=False)
    scheduler: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    seed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    width: Mapped[int] = mapped_column(Integer, default=1024, nullable=False)
    height: Mapped[int] = mapped_column(Integer, default=1024, nullable=False)
    batch_size: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String, default="Tried", nullable=False)
    source: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notion_page_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    comfyui_workflow_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.current_timestamp(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.current_timestamp(), nullable=False
    )

    # Relationships
    model: Mapped[Optional["Model"]] = relationship("Model", back_populates="runs")
    images: Mapped[List["Image"]] = relationship(
        "Image", back_populates="run", cascade="all, delete-orphan"
    )
    loras: Mapped[List["RunLora"]] = relationship(
        "RunLora", back_populates="run", cascade="all, delete-orphan"
    )
    tags: Mapped[List["RunTag"]] = relationship(
        "RunTag", back_populates="run", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        """文字列表現を返します."""
        return f"<Run(id={self.run_id}, title='{self.title}', status='{self.status}')>"


class Image(Base):
    """生成画像テーブル.
    
    実行履歴に紐づく生成画像の情報を管理します。
    """

    __tablename__ = "images"

    image_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("runs.run_id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String, nullable=False)
    filepath: Mapped[str] = mapped_column(String, nullable=False)
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    hash: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    image_metadata: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.current_timestamp(), nullable=False
    )

    # Relationships
    run: Mapped["Run"] = relationship("Run", back_populates="images")

    def __repr__(self) -> str:
        """文字列表現を返します."""
        return f"<Image(id={self.image_id}, filename='{self.filename}')>"


class Tag(Base):
    """タグテーブル.
    
    実行履歴の分類用タグを管理します。
    """

    __tablename__ = "tags"

    tag_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.current_timestamp(), nullable=False
    )

    # Relationships
    runs: Mapped[List["RunTag"]] = relationship(
        "RunTag", back_populates="tag", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        """文字列表現を返します."""
        return f"<Tag(id={self.tag_id}, name='{self.name}', category='{self.category}')>"


class RunLora(Base):
    """実行履歴とLoRAの関連付けテーブル.
    
    多対多の関係を管理します。
    """

    __tablename__ = "run_loras"

    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("runs.run_id", ondelete="CASCADE"), primary_key=True
    )
    lora_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("models.model_id", ondelete="CASCADE"), primary_key=True
    )
    weight: Mapped[float] = mapped_column(REAL, default=1.0, nullable=False)

    # Relationships
    run: Mapped["Run"] = relationship("Run", back_populates="loras")
    lora_model: Mapped["Model"] = relationship(
        "Model", foreign_keys=[lora_id], back_populates="lora_runs"
    )

    def __repr__(self) -> str:
        """文字列表現を返します."""
        return f"<RunLora(run_id={self.run_id}, lora_id={self.lora_id}, weight={self.weight})>"


class RunTag(Base):
    """実行履歴とタグの関連付けテーブル.
    
    多対多の関係を管理します。
    """

    __tablename__ = "run_tags"

    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("runs.run_id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tags.tag_id", ondelete="CASCADE"), primary_key=True
    )

    # Relationships
    run: Mapped["Run"] = relationship("Run", back_populates="tags")
    tag: Mapped["Tag"] = relationship("Tag", back_populates="runs")

    def __repr__(self) -> str:
        """文字列表現を返します."""
        return f"<RunTag(run_id={self.run_id}, tag_id={self.tag_id})>"


# Auto-update triggers for updated_at fields
@event.listens_for(Model, "before_update")
def update_model_timestamp(mapper: Any, connection: Any, target: Model) -> None:
    """Modelテーブルのupdated_atを自動更新します."""
    target.updated_at = datetime.utcnow()


@event.listens_for(Run, "before_update")
def update_run_timestamp(mapper: Any, connection: Any, target: Run) -> None:
    """Runテーブルのupdated_atを自動更新します."""
    target.updated_at = datetime.utcnow()