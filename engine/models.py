from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProcessBlock:
    id: int
    type: str
    x: float
    y: float
    process_time: float
    capacity: int = 1
    custom_name: str = ""
    width: int = 150
    height: int = 80


@dataclass
class ProcessConnection:
    id: int
    from_block: int
    to_block: int


@dataclass
class Scenario:
    blocks: list[ProcessBlock] = field(default_factory=list)
    connections: list[ProcessConnection] = field(default_factory=list)

    def next_block_id(self) -> int:
        if not self.blocks:
            return 1
        return max(block.id for block in self.blocks) + 1

    def next_connection_id(self) -> int:
        if not self.connections:
            return 1
        return max(connection.id for connection in self.connections) + 1

    def add_block(
        self,
        block_type: str,
        x: float,
        y: float,
        process_time: float,
        capacity: int = 1,
        custom_name: str = "",
        block_id: int | None = None,
    ) -> ProcessBlock:
        block = ProcessBlock(
            id=block_id if block_id is not None else self.next_block_id(),
            type=block_type,
            x=x,
            y=y,
            process_time=process_time,
            capacity=capacity,
            custom_name=custom_name,
        )
        self.blocks.append(block)
        return block

    def delete_block(self, block_id: int) -> None:
        self.blocks = [block for block in self.blocks if block.id != block_id]
        self.connections = [
            connection
            for connection in self.connections
            if connection.from_block != block_id and connection.to_block != block_id
        ]

    def add_connection(
        self,
        from_block: int,
        to_block: int,
        connection_id: int | None = None,
    ) -> ProcessConnection:
        if from_block == to_block:
            raise ValueError("A block cannot connect to itself.")

        block_ids = {block.id for block in self.blocks}
        if from_block not in block_ids or to_block not in block_ids:
            raise ValueError("Both connection endpoints must exist in the scenario.")

        duplicate = any(
            connection.from_block == from_block and connection.to_block == to_block
            for connection in self.connections
        )
        if duplicate:
            raise ValueError("Connection already exists.")

        connection = ProcessConnection(
            id=connection_id if connection_id is not None else self.next_connection_id(),
            from_block=from_block,
            to_block=to_block,
        )
        self.connections.append(connection)
        return connection

    def delete_connection(self, connection_id: int) -> None:
        self.connections = [
            connection for connection in self.connections if connection.id != connection_id
        ]
