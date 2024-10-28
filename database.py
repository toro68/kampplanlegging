# database.py
import sqlite3
import pandas as pd
import streamlit as st
import json
import os
from pathlib import Path
import logging
from io import StringIO  # Legg til denne importen øverst

logger = logging.getLogger(__name__)

class DatabaseHandler:
    def __init__(self, data_dir=Path("data"), session_state=None):
        """Initialiserer DatabaseHandler med valgfri session_state"""
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.db_path = self.data_dir / "kampdata.db"
        self.session_state = session_state if session_state is not None else st.session_state
        self._opprett_tabeller()

    def _opprett_tabeller(self):
        """Oppretter nødvendige tabeller hvis de ikke eksisterer"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Spillere tabell
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS spillere (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        data TEXT NOT NULL
                    )
                """)
                
                # Kampinnstillinger tabell
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS kampinnstillinger (
                        kamptid INTEGER NOT NULL,
                        antall_paa_banen INTEGER NOT NULL
                    )
                """)
                
                # Perioder tabell
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS perioder (
                        perioder TEXT NOT NULL
                    )
                """)

                conn.commit()
        except sqlite3.Error as e:
            logging.error(f"Feil ved opprettelse av tabeller: {e}")
            raise

    def lagre_spillere(self):
        """Lagrer spillerdata"""
        try:
            if not hasattr(self.session_state, 'spilletid_df'):
                logging.warning("Ingen spilletid_df funnet i session_state")
                return
                
            df_json = self.session_state.spilletid_df.to_json(orient='split')
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM spillere")
                conn.execute("INSERT INTO spillere (data) VALUES (?)", (df_json,))
                conn.commit()
        except Exception as e:
            logging.error(f"Feil ved lagring av spillere: {e}")
            raise

    def last_spillere(self):
        """Laster spillerdata"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT data FROM spillere LIMIT 1")
                row = cursor.fetchone()
                if row:
                    try:
                        df = pd.read_json(StringIO(row[0]), orient='split', convert_dates=False)
                        bool_columns = df.select_dtypes(include=['bool']).columns
                        for col in bool_columns:
                            df[col] = df[col].astype(bool)
                        self.session_state.spilletid_df = df
                    except ValueError as e:
                        logging.error(f"Feil ved parsing av spillerdata: {e}")
                        self.session_state.spilletid_df = pd.DataFrame()
        except sqlite3.Error as e:
            logging.error(f"Database feil ved lasting av spillere: {e}")
            self.session_state.spilletid_df = pd.DataFrame()

    def lagre_kampinnstillinger(self):
        """Lagrer kampinnstillinger"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM kampinnstillinger")
                conn.execute(
                    "INSERT INTO kampinnstillinger (kamptid, antall_paa_banen) VALUES (?, ?)",
                    (self.session_state.kamptid, self.session_state.antall_paa_banen)
                )
                conn.commit()
        except Exception as e:
            logging.error(f"Feil ved lagring av kampinnstillinger: {e}")
            raise

    def last_kampinnstillinger(self):
        """Laster kampinnstillinger"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT kamptid, antall_paa_banen FROM kampinnstillinger LIMIT 1")
                row = cursor.fetchone()
                if row:
                    self.session_state.kamptid = row[0]
                    self.session_state.antall_paa_banen = row[1]
        except Exception as e:
            logging.error(f"Feil ved lasting av kampinnstillinger: {e}")
            raise

    def lagre_perioder(self):
        """Lagrer perioder"""
        try:
            if not hasattr(self.session_state, 'perioder'):
                logging.warning("Ingen perioder funnet i session_state")
                return
                
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM perioder")
                conn.execute(
                    "INSERT INTO perioder (perioder) VALUES (?)",
                    (json.dumps(self.session_state.perioder),)
                )
                conn.commit()
        except Exception as e:
            logging.error(f"Feil ved lagring av perioder: {e}")
            raise

    def last_perioder(self):
        """Laster perioder"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT perioder FROM perioder LIMIT 1")
                row = cursor.fetchone()
                if row:
                    try:
                        self.session_state.perioder = json.loads(row[0])
                    except json.JSONDecodeError as e:
                        logging.error(f"Feil ved parsing av perioder: {e}")
                        self.session_state.perioder = []
                else:
                    self.session_state.perioder = []
        except sqlite3.Error as e:
            logging.error(f"Database feil ved lasting av perioder: {e}")
            self.session_state.perioder = []

    def lagre_alt(self):
        """Lagrer all data"""
        try:
            self.lagre_spillere()
            self.lagre_kampinnstillinger()
            self.lagre_perioder()
        except Exception as e:
            logging.error(f"Feil ved lagring av all data: {e}")
            raise

    def last_alt(self):
        """Laster all data"""
        try:
            self.last_spillere()
            self.last_kampinnstillinger()
            self.last_perioder()
        except Exception as e:
            logging.error(f"Feil ved lasting av all data: {e}")
            raise

    def lagre_spilletid(self):
        """
        Lagrer spilletidsdata. Dette er en spesialisert versjon av lagre_spillere()
        som fokuserer på spilletidsrelaterte kolonner.
        
        Note: Denne metoden er inkludert for bakoverkompatibilitet og 
        funksjonell likhet med lagre_spillere().
        """
        try:
            if not hasattr(self.session_state, 'spilletid_df'):
                logging.warning("Ingen spilletid_df funnet i session_state")
                return
                
            df_json = self.session_state.spilletid_df.to_json(orient='split')
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM spillere")
                conn.execute("INSERT INTO spillere (data) VALUES (?)", (df_json,))
                conn.commit()
        except Exception as e:
            logging.error(f"Feil ved lagring av spilletid: {e}")
            raise

    def last_spilletid(self):
        """
        Laster spilletidsdata. Dette er en spesialisert versjon av last_spillere()
        som fokuserer på spilletidsrelaterte kolonner.
        
        Note: Denne metoden er inkludert for bakoverkompatibilitet og 
        funksjonell likhet med last_spillere().
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT data FROM spillere LIMIT 1")
                row = cursor.fetchone()
                if row:
                    try:
                        df = pd.read_json(StringIO(row[0]), orient='split', convert_dates=False)
                        bool_columns = df.select_dtypes(include=['bool']).columns
                        for col in bool_columns:
                            df[col] = df[col].astype(bool)
                        self.session_state.spilletid_df = df
                    except ValueError as e:
                        logging.error(f"Feil ved parsing av spilletidsdata: {e}")
                        if 'spilletid_df' not in self.session_state:
                            self.session_state.spilletid_df = pd.DataFrame()
        except sqlite3.Error as e:
            logging.error(f"Database feil ved lasting av spilletid: {e}")
            if 'spilletid_df' not in self.session_state:
                self.session_state.spilletid_df = pd.DataFrame()
