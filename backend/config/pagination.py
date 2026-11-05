from rest_framework.pagination import CursorPagination


class NewestFirst(CursorPagination):
    ordering = "-created_at"
    page_size = 20
