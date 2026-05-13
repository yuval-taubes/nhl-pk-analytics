"""
Database connection handler for NHL analytics data.
"""

import psycopg2
import pandas as pd
import logging

logger = logging.getLogger(__name__)

class DatabaseConnection:
    """PostgreSQL connection wrapper."""
    
    def __init__(self, config=None):
        if config is None:
            from config import DB_CONFIG
            config = DB_CONFIG
        
        self.config = config
        self.conn = None
        self.cursor = None
    
    def connect(self):
        """Establish database connection."""
        try:
            self.conn = psycopg2.connect(**self.config)
            self.cursor = self.conn.cursor()
            logger.info(f"Connected to database: {self.config['database']}")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise
    
    def query_to_df(self, query, params=None):
        """Execute query and return results as DataFrame."""
        try:
            if params:
                return pd.read_sql_query(query, self.conn, params=params)
            return pd.read_sql_query(query, self.conn)
        except Exception as e:
            logger.error(f"Query failed: {e}")
            logger.debug(f"Query: {query[:200]}...")
            raise
    
    def execute(self, query, params=None):
        """Execute a query and return rowcount."""
        try:
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
            self.conn.commit()
            return self.cursor.rowcount
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Execute failed: {e}")
            raise
    
    def close(self):
        """Close database connection."""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")