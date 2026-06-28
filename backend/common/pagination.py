"""Cursor pagination (contract §3.7).

List endpoints return ``{ "next", "previous", "results" }``. Cursor pagination
keeps results stable as rows are added during paging.
"""

from __future__ import annotations

from rest_framework.pagination import CursorPagination

from core import constants


class DefaultCursorPagination(CursorPagination):
    page_size = constants.DEFAULT_PAGE_SIZE
    page_size_query_param = "page_size"
    max_page_size = constants.MAX_PAGE_SIZE
    ordering = "-created_at"
