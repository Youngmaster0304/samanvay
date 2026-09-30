"""Declarative base for SQLAlchemy models. Models are added from Stage 1 onwards."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
