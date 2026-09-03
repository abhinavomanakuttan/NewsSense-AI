import math
from collections.abc import Sequence
from typing import TypeVar

T = TypeVar("T")


class Paginator:
    def __init__(self, items: Sequence, total: int, page: int, page_size: int):
        self.items = items
        self.total = total
        self.page = page
        self.page_size = page_size
        self.total_pages = max(1, math.ceil(total / page_size))
        self.has_next = page < self.total_pages
        self.has_prev = page > 1

    def to_dict(self) -> dict:
        return {
            "items": self.items,
            "total": self.total,
            "page": self.page,
            "page_size": self.page_size,
            "total_pages": self.total_pages,
            "has_next": self.has_next,
            "has_prev": self.has_prev,
        }
