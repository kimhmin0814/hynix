import json
import pickle
from typing import Any, Dict, Iterator, Optional

import oracledb  # pip install oracledb
from langgraph.checkpoint.base import BaseCheckpointSaver, CheckpointTuple, Checkpoint, CheckpointMetadata
from langchain_core.runnables import RunnableConfig


class OracleCheckpointSaver(BaseCheckpointSaver):
    def __init__(self, user: str, password: str, dsn: str):
        """
        user     : Oracle DB 사용자명
        password : Oracle DB 비밀번호
        dsn      : 'host:port/service_name' 형식
        """
        super().__init__()
        self.conn = oracledb.connect(user=user, password=password, dsn=dsn)
        self._setup_table()

    def _setup_table(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            BEGIN
                EXECUTE IMMEDIATE '
                    CREATE TABLE langgraph_checkpoints (
                        thread_id     VARCHAR2(200),
                        checkpoint_id VARCHAR2(200),
                        checkpoint    BLOB,
                        metadata      CLOB,
                        parent_id     VARCHAR2(200),
                        created_at    TIMESTAMP DEFAULT SYSTIMESTAMP,
                        PRIMARY KEY (thread_id, checkpoint_id)
                    )
                ';
            EXCEPTION
                WHEN OTHERS THEN
                    IF SQLCODE != -955 THEN RAISE; END IF;
            END;
        """)
        self.conn.commit()
        cursor.close()

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        thread_id = config["configurable"]["thread_id"]
        checkpoint_id = config["configurable"].get("checkpoint_id")

        cursor = self.conn.cursor()
        if checkpoint_id:
            cursor.execute("""
                SELECT checkpoint, metadata, parent_id, checkpoint_id
                FROM langgraph_checkpoints
                WHERE thread_id = :1 AND checkpoint_id = :2
            """, [thread_id, checkpoint_id])
        else:
            cursor.execute("""
                SELECT checkpoint, metadata, parent_id, checkpoint_id
                FROM langgraph_checkpoints
                WHERE thread_id = :1
                ORDER BY created_at DESC
                FETCH FIRST 1 ROWS ONLY
            """, [thread_id])

        row = cursor.fetchone()
        cursor.close()

        if not row:
            return None

        checkpoint_blob, metadata_str, parent_id, cp_id = row
        checkpoint = pickle.loads(checkpoint_blob.read())
        metadata = json.loads(metadata_str)

        config_with_id = {
            **config,
            "configurable": {**config["configurable"], "checkpoint_id": cp_id}
        }
        parent_config = (
            {**config, "configurable": {**config["configurable"], "checkpoint_id": parent_id}}
            if parent_id else None
        )

        return CheckpointTuple(
            config=config_with_id,
            checkpoint=checkpoint,
            metadata=metadata,
            parent_config=parent_config,
        )

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: Any,
    ) -> RunnableConfig:
        thread_id = config["configurable"]["thread_id"]
        checkpoint_id = checkpoint["id"]
        parent_id = config["configurable"].get("checkpoint_id")

        checkpoint_blob = pickle.dumps(checkpoint)
        metadata_str = json.dumps(metadata)

        cursor = self.conn.cursor()
        cursor.execute("""
            MERGE INTO langgraph_checkpoints t
            USING DUAL ON (t.thread_id = :1 AND t.checkpoint_id = :2)
            WHEN MATCHED THEN
                UPDATE SET checkpoint = :3, metadata = :4, parent_id = :5
            WHEN NOT MATCHED THEN
                INSERT (thread_id, checkpoint_id, checkpoint, metadata, parent_id)
                VALUES (:1, :2, :3, :4, :5)
        """, [thread_id, checkpoint_id, checkpoint_blob, metadata_str, parent_id])
        self.conn.commit()
        cursor.close()

        return {
            **config,
            "configurable": {**config["configurable"], "checkpoint_id": checkpoint_id}
        }

    def list(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[Dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> Iterator[CheckpointTuple]:
        thread_id = config["configurable"]["thread_id"] if config else None

        query = """
            SELECT checkpoint, metadata, parent_id, checkpoint_id
            FROM langgraph_checkpoints
        """
        params = []

        if thread_id:
            query += " WHERE thread_id = :1"
            params.append(thread_id)

        query += " ORDER BY created_at DESC"

        if limit:
            query += f" FETCH FIRST {limit} ROWS ONLY"

        cursor = self.conn.cursor()
        cursor.execute(query, params)

        for row in cursor:
            checkpoint_blob, metadata_str, parent_id, cp_id = row
            checkpoint = pickle.loads(checkpoint_blob.read())
            metadata = json.loads(metadata_str)

            cfg = {"configurable": {"thread_id": thread_id, "checkpoint_id": cp_id}}
            parent_cfg = (
                {"configurable": {"thread_id": thread_id, "checkpoint_id": parent_id}}
                if parent_id else None
            )
            yield CheckpointTuple(
                config=cfg,
                checkpoint=checkpoint,
                metadata=metadata,
                parent_config=parent_cfg,
            )

        cursor.close()

    def close(self):
        self.conn.close()
