from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field


class TelegramUser(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    is_bot: bool = False
    first_name: str = ""
    username: str | None = None


class TelegramChat(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    type: str
    title: str | None = None
    username: str | None = None


class TelegramMessage(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    message_id: int
    date: int
    chat: TelegramChat
    sender: TelegramUser | None = Field(default=None, alias="from")
    text: str | None = None


class TelegramUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    update_id: int
    message: TelegramMessage | None = None


@dataclass(frozen=True)
class TelegramQueryRequest:
    command: str
    args: tuple[str, ...]
    raw_text: str


def parse_telegram_query(text: str | None) -> TelegramQueryRequest | None:
    if not text or not text.strip():
        return None

    raw_text = text.strip()
    if not raw_text.startswith("/"):
        return TelegramQueryRequest(
            command="query",
            args=(raw_text,),
            raw_text=raw_text,
        )

    parts = raw_text.split()
    command = parts[0][1:].split("@", 1)[0].lower()
    if not command:
        return None
    return TelegramQueryRequest(
        command=command,
        args=tuple(parts[1:]),
        raw_text=raw_text,
    )
