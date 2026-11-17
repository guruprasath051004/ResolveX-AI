"""Postgres-persisted checkpointer for LangGraph agent workflow."""
import json
from typing import Any, Dict, Optional
from datetime import datetime

from langgraph.checkpoint.memory import MemorySaver
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    Checkpoint,
    CheckpointMetadata,
    ChannelVersions,
    CheckpointTuple,
)

class PostgresSaver(MemorySaver):
    """LangGraph checkpointer that maintains in-memory state and persists checkpoints to PostgreSQL / DB.
    
    Provides thread isolation, crash-recovery, and approval pause-and-resume capability.
    """

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        cfg = dict(config)
        if "configurable" not in cfg:
            cfg["configurable"] = {}
        else:
            cfg["configurable"] = dict(cfg["configurable"])
        if "checkpoint_ns" not in cfg["configurable"]:
            cfg["configurable"]["checkpoint_ns"] = ""

        res = super().put(cfg, checkpoint, metadata, new_versions)
        
        # Persist checkpoint to database
        try:
            thread_id = config.get("configurable", {}).get("thread_id", "default")
            checkpoint_id = str(checkpoint.get("id", ""))
            
            # Serialize state values
            checkpoint_payload = {
                "thread_id": thread_id,
                "checkpoint_id": checkpoint_id,
                "timestamp": datetime.utcnow().isoformat(),
                "values": checkpoint.get("channel_values", {}),
            }
            
            from backend.database import SessionLocal
            from backend.models import AgentCheckpoint
            
            db = SessionLocal()
            try:
                record = AgentCheckpoint(
                    thread_id=thread_id,
                    checkpoint_id=checkpoint_id,
                    checkpoint_data=json.dumps(checkpoint_payload, default=str),
                )
                db.add(record)
                db.commit()
            finally:
                db.close()
        except Exception as e:
            # Logging without interrupting workflow execution
            print(f"[PostgresSaver] DB Checkpoint notice: {e}")
            
        return res

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        return self.put(config, checkpoint, metadata, new_versions)

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        cfg = dict(config)
        if "configurable" not in cfg:
            cfg["configurable"] = {}
        else:
            cfg["configurable"] = dict(cfg["configurable"])
        if "checkpoint_ns" not in cfg["configurable"]:
            cfg["configurable"]["checkpoint_ns"] = ""
        try:
            return super().get_tuple(cfg)
        except Exception:
            return None

    def get_latest_checkpoint_data(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve latest serialized checkpoint state from database for thread."""
        from backend.database import SessionLocal
        from backend.models import AgentCheckpoint
        
        db = SessionLocal()
        try:
            record = (
                db.query(AgentCheckpoint)
                .filter(AgentCheckpoint.thread_id == thread_id)
                .order_by(AgentCheckpoint.id.desc())
                .first()
            )
            if record and record.checkpoint_data:
                return json.loads(record.checkpoint_data)
            return None
        except Exception as e:
            print(f"[PostgresSaver] Failed to load checkpoint from DB: {e}")
            return None
        finally:
            db.close()
