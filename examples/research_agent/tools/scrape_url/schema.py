from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl


class ScrapeUrlInput(BaseModel):
    url: HttpUrl
    formats: list[Literal["markdown", "text", "html", "links"]] = Field(
        default_factory=lambda: ["markdown"]
    )


class ScrapeUrlOutput(BaseModel):
    url: HttpUrl
    title: str | None = None
    markdown: str | None = None
    text: str | None = None
    html: str | None = None
    status_code: int
    provider: str
    provider_metadata: dict[str, Any] = Field(default_factory=dict)
