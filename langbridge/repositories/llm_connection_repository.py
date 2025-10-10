from sqlalchemy.orm import Session

from db.agent import LLMConnection
from .base import BaseRepository

class LLMConnectionRepository(BaseRepository):
    def __init__(self, session: Session):
        super().__init__(session, LLMConnection)