from __future__ import annotations


class AppError(Exception):
    """일관된 {detail, code} 오류 응답을 만들기 위한 애플리케이션 예외."""

    def __init__(self, status_code: int, code: str, detail: str) -> None:
        self.status_code = status_code
        self.code = code
        self.detail = detail
        super().__init__(detail)
