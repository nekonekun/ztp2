from typing import Any

from sqlalchemy.ext.declarative import as_declarative, declared_attr


@as_declarative()
class ZTPBase:
    id: Any
    __name__: str

    # Generate __tablename__ automatically
    @declared_attr
    def __tablename__(cls) -> str:
        return cls.__name__.lower()

    def __repr__(self):
        return self.__class__.__name__ + '(' + ', '.join([f'{k}: {v}' for k, v in self.__dict__.items()]) + ')'


@as_declarative()
class KeaBase:
    id: Any
    __name__: str

    # Generate __tablename__ automatically
    @declared_attr
    def __tablename__(cls) -> str:
        return cls.__name__.lower()

    def __repr__(self):
        return self.__class__.__name__ + '(' + ', '.join([f'{k}: {v}' for k, v in self.__dict__.items()]) + ')'
