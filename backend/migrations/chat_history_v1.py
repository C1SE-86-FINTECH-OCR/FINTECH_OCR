"""Add server-side chat metadata without replacing existing history."""
from sqlalchemy import inspect, text

from app.models import ChatMessage, ChatTurn, Conversation


def upgrade(connection):
    columns = {column['name'] for column in inspect(connection).get_columns('conversations')}
    if 'updated_at' not in columns:
        datatype = 'TIMESTAMP WITH TIME ZONE' if connection.dialect.name == 'postgresql' else 'DATETIME'
        connection.execute(text(f'ALTER TABLE conversations ADD COLUMN updated_at {datatype}'))
        connection.execute(text("""
            UPDATE conversations SET updated_at = COALESCE(
                (SELECT MAX(created_at) FROM chat_messages WHERE conversation_id = conversations.id),
                created_at
            )
        """))
    ChatTurn.__table__.create(connection, checkfirst=True)
    for model in (Conversation, ChatMessage):
        for index in model.__table__.indexes:
            index.create(connection, checkfirst=True)
    return 'ready'
