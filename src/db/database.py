"""
Database connection and session management functionality.
Provides utilities for connecting to the database and managing sessions.
"""
import os
import logging
import contextlib
from typing import AsyncGenerator, Any, Optional

import sqlite3
import aiosqlite
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

# Default SQLite database path
DEFAULT_DB_PATH = os.path.join('data', 'operational_data.db')

@asynccontextmanager
async def get_db_session_context(db_path: Optional[str] = None) -> AsyncGenerator[aiosqlite.Connection, None]:
    """
    Async context manager for database sessions.
    
    Args:
        db_path: Optional path to the SQLite database. Defaults to DEFAULT_DB_PATH.
        
    Yields:
        An aiosqlite connection object
    
    Example:
        async with get_db_session_context() as db:
            await db.execute("SELECT * FROM resource_metrics")
            results = await db.fetchall()
    """
    # Use default path if none provided
    db_path = db_path or DEFAULT_DB_PATH
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    
    conn = None
    try:
        # Connect to database
        conn = await aiosqlite.connect(db_path)
        # Enable foreign keys
        await conn.execute("PRAGMA foreign_keys = ON")
        # Return connection for use in context
        yield conn
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise
    finally:
        # Close connection when context exits
        if conn:
            await conn.close()
            logger.debug("Database connection closed")

async def initialize_db(db_path: Optional[str] = None, schema_path: Optional[str] = None) -> bool:
    """
    Initialize the database with schema if it doesn't exist.
    
    Args:
        db_path: Path to the SQLite database file. Defaults to DEFAULT_DB_PATH.
        schema_path: Path to the SQL schema file. Defaults to src/db/schema.sql.
        
    Returns:
        True if initialization was successful, False otherwise.
    """
    db_path = db_path or DEFAULT_DB_PATH
    schema_path = schema_path or os.path.join('src', 'db', 'schema.sql')
    
    # Check if schema file exists
    if not os.path.exists(schema_path):
        logger.error(f"Schema file not found: {schema_path}")
        return False
    
    try:
        # Read schema SQL
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
        
        # Initialize database
        async with get_db_session_context(db_path) as conn:
            await conn.executescript(schema_sql)
            await conn.commit()
            logger.info(f"Database initialized successfully at {db_path}")
            return True
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        return False 