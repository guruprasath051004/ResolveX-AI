"""SQLAlchemy model for knowledge document metadata and searchable text."""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, Uuid, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
import uuid

from ..database import Base

class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    category = Column(String, nullable=False)
    content = Column(Text)
    source_path = Column(Text, nullable=False)
    file_path = Column(Text)
    doc_type = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    version_number = Column(Integer, nullable=False, default=1, server_default="1")
    content_hash = Column(String(64), index=True)
    index_status = Column(String, nullable=False, default="not_indexed", server_default="not_indexed")
    index_error = Column(Text)
    chunk_count = Column(Integer, nullable=False, default=0, server_default="0")
    embedding_model = Column(String)
    indexed_at = Column(DateTime)
    versions = relationship(
        "KnowledgeDocumentVersion",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="KnowledgeDocumentVersion.version_number.desc()",
    )

    def __repr__(self) -> str:
        return f"<KnowledgeDocument {self.id} {self.title}>"


class KnowledgeDocumentVersion(Base):
    __tablename__ = "knowledge_document_versions"

    id = Column(Integer, primary_key=True)
    document_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number = Column(Integer, nullable=False)
    content_hash = Column(String(64), nullable=False)
    content = Column(Text)
    source_path = Column(Text, nullable=False)
    doc_type = Column(String)
    index_status = Column(String, nullable=False)
    chunk_count = Column(Integer, nullable=False, default=0, server_default="0")
    embedding_model = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    document = relationship("KnowledgeDocument", back_populates="versions")

    __table_args__ = (
        UniqueConstraint("document_id", "version_number", name="uq_knowledge_document_version"),
    )

