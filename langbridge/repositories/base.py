from sqlalchemy.orm import Session

class BaseRepository:
    def __init__(self, session: Session, model):
        self._session = session
        self._model = model

    def add(self, instance):
        self._session.add(instance)

    def delete(self, instance):
        self._session.delete(instance)

    def get_by_id(self, id):
        return self._session.query(self._model).get(id)
    
    def get_all(self):
        return self._session.query(self._model).all()