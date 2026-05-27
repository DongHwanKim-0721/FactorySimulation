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
            raise ValueError("같은 블록끼리는 연결할 수 없습니다.")

        block_ids = {block.id for block in self.blocks}
        if from_block not in block_ids or to_block not in block_ids:
            raise ValueError("연결하려는 블록이 시나리오에 있어야 합니다.")

        duplicate = any(
            connection.from_block == from_block and connection.to_block == to_block
            for connection in self.connections
        )
        if duplicate:
            raise ValueError("이미 존재하는 연결입니다.")

        if self._would_create_cycle(from_block, to_block):
            raise ValueError("순환 흐름은 지원하지 않습니다.")

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

    def _would_create_cycle(self, from_block: int, to_block: int) -> bool:
        stack = [to_block]
        visited: set[int] = set()

        while stack:
            current = stack.pop()
            if current == from_block:
                return True
            if current in visited:
                continue
            visited.add(current)

            stack.extend(
                connection.to_block
                for connection in self.connections
                if connection.from_block == current
            )

        return False
