import unittest
import pandas as pd
import streamlit as st
from database import DatabaseHandler
import os
from pathlib import Path
import tempfile
import sqlite3
import logging
import warnings
from unittest.mock import patch, MagicMock

# Undertrykk advarsler fra Streamlit
warnings.filterwarnings('ignore', module='streamlit')

# Konfigurer logging
logging.getLogger('streamlit').setLevel(logging.ERROR)
logging.getLogger('streamlit.runtime').setLevel(logging.ERROR)
logging.getLogger('streamlit.runtime.scriptrunner').setLevel(logging.ERROR)

class MockSessionState(dict):
    """Mock for Streamlit session state som oppfører seg som både dict og objekt"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__dict__ = self
    
    def __getattr__(self, key):
        if key not in self:
            raise AttributeError(f"st.session_state has no attribute {key}")
        return self[key]

class TestDatabaseHandler(unittest.TestCase):
    def setUp(self):
        """Kjører før hver test"""
        # Opprett en midlertidig testmappe
        self.temp_dir = tempfile.mkdtemp()
        self.test_dir = Path(self.temp_dir)
        
        # Opprett standard test DataFrame
        self.test_df = pd.DataFrame({
            'Posisjoner': [['Keeper'], ['Back']],
            'Aktiv posisjon': ['Keeper', 'Back'],
            'Tilgjengelig': [True, True],
            'Total spilletid': [0, 0],
            'Differanse': [0, 0],
            'Mål spilletid': [0, 0]
        }, index=['Spiller1', 'Spiller2'])
        
        # Definer standard perioder
        self.perioder = ['0-15', '15-25']
        
        # Legg til periodekolonner
        for periode in self.perioder:
            self.test_df[periode] = False
            
        # Opprett en mock session state
        self.mock_session_state = MockSessionState({
            'spilletid_df': self.test_df.copy(),
            'kamptid': 80,
            'antall_paa_banen': 9,
            'perioder': self.perioder.copy()
        })
        
        # Mock st.session_state
        patcher = patch('streamlit.session_state', self.mock_session_state)
        patcher.start()
        self.addCleanup(patcher.stop)
        
        # Opprett DatabaseHandler med mock session state
        self.db = DatabaseHandler(
            data_dir=self.test_dir,
            session_state=self.mock_session_state
        )
        
        # Opprett tabeller
        self.db._opprett_tabeller()

    def tearDown(self):
        """Rydd opp etter testene"""
        import shutil
        if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_database_creation(self):
        """Tester at databasen blir opprettet korrekt"""
        self.assertTrue(os.path.exists(self.db.db_path))

    def test_kampinnstillinger(self):
        """Tester lagring og lasting av kampinnstillinger"""
        original_kamptid = self.mock_session_state.kamptid
        original_antall = self.mock_session_state.antall_paa_banen
        
        # Lagre innstillinger
        self.db.lagre_kampinnstillinger()
        
        # Endre verdiene
        self.mock_session_state.kamptid = 60
        self.mock_session_state.antall_paa_banen = 7
        
        # Last inn igjen
        self.db.last_kampinnstillinger()
        
        # Sjekk verdiene
        self.assertEqual(self.mock_session_state.kamptid, original_kamptid)
        self.assertEqual(self.mock_session_state.antall_paa_banen, original_antall)

    def test_spillere(self):
        """Tester lagring og lasting av spillerdata"""
        original_df = self.mock_session_state.spilletid_df.copy()
        
        # Lagre data
        self.db.lagre_spillere()
        
        # Endre data
        self.mock_session_state.spilletid_df.at['Spiller1', 'Aktiv posisjon'] = 'Midtbane'
        
        # Last inn igjen
        self.db.last_spillere()
        
        # Sjekk at dataene er like
        pd.testing.assert_frame_equal(self.mock_session_state.spilletid_df, original_df)

    def test_spilletid(self):
        """Tester lagring og lasting av spilletidsdata"""
        original_df = self.mock_session_state.spilletid_df.copy()
        
        # Lagre data
        self.db.lagre_spilletid()
        
        # Endre noen verdier
        self.mock_session_state.spilletid_df.at['Spiller1', '0-15'] = True
        
        # Last inn igjen
        self.db.last_spilletid()
        
        # Sjekk at dataene er like
        pd.testing.assert_frame_equal(self.mock_session_state.spilletid_df, original_df)

    def test_perioder(self):
        """Tester lagring og lasting av perioder"""
        original_perioder = self.perioder.copy()
        
        # Lagre perioder
        self.db.lagre_perioder()
        
        # Endre perioder
        self.mock_session_state.perioder = ['0-10', '10-20']
        
        # Last inn igjen
        self.db.last_perioder()
        
        # Sjekk at periodene er like
        self.assertEqual(self.mock_session_state.perioder, original_perioder)

    def test_lagre_alt(self):
        """Tester lagring av all data samtidig"""
        original_df = self.test_df.copy()
        original_kamptid = self.mock_session_state.kamptid
        original_antall = self.mock_session_state.antall_paa_banen
        original_perioder = self.perioder.copy()
        
        # Lagre alt
        self.db.lagre_alt()
        
        # Endre alle verdier
        self.mock_session_state.spilletid_df.at['Spiller1', 'Aktiv posisjon'] = 'Midtbane'
        self.mock_session_state.kamptid = 60
        self.mock_session_state.antall_paa_banen = 7
        self.mock_session_state.perioder = ['0-10', '10-20']
        
        # Last inn igjen
        self.db.last_alt()
        
        # Sjekk alle verdier
        pd.testing.assert_frame_equal(self.mock_session_state.spilletid_df, original_df)
        self.assertEqual(self.mock_session_state.kamptid, original_kamptid)
        self.assertEqual(self.mock_session_state.antall_paa_banen, original_antall)
        self.assertEqual(self.mock_session_state.perioder, original_perioder)

    def test_database_error_handling(self):
        """Tester feilhåndtering i databaseoperasjoner"""
        with patch('sqlite3.connect') as mock_connect:
            mock_connect.side_effect = sqlite3.Error("Test error")
            with self.assertRaises(Exception):
                self.db.lagre_spillere()

    def test_database_corruption(self):
        """Tester håndtering av korrupt database"""
        # Skriv ugyldig data til databasen
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DROP TABLE IF EXISTS spillere")
            cursor.execute("CREATE TABLE IF NOT EXISTS spillere (data TEXT)")
            cursor.execute('INSERT INTO spillere (data) VALUES (?)', ('invalid json',))
            conn.commit()
        
        # Last inn data - skal ikke feile, men returnere tom DataFrame
        self.db.last_spillere()
        self.assertIsInstance(self.mock_session_state.spilletid_df, pd.DataFrame)

    def test_missing_tables(self):
        """Tester opprettelse av manglende tabeller"""
        # Slett alle tabeller
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DROP TABLE IF EXISTS spillere")
            cursor.execute("DROP TABLE IF EXISTS kampinnstillinger")
            cursor.execute("DROP TABLE IF EXISTS perioder")
            conn.commit()
        
        # Opprett tabellene på nytt
        self.db._opprett_tabeller()
        
        # Sjekk at tabellene eksisterer
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}
            
            self.assertIn('spillere', tables)
            self.assertIn('kampinnstillinger', tables)
            self.assertIn('perioder', tables)

    def test_concurrent_access(self):
        """Tester samtidig tilgang til databasen"""
        # Opprett en ny DatabaseHandler-instans med samme temp_dir og mock session state
        db2 = DatabaseHandler(
            data_dir=self.test_dir,
            session_state=self.mock_session_state
        )
        
        # Lagre data med første handler
        self.db.lagre_spillere()
        
        # Modifiser og lagre med andre handler
        self.mock_session_state.spilletid_df.at['Spiller1', 'Aktiv posisjon'] = 'Midtbane'
        db2.lagre_spillere()
        
        # Last inn med første handler
        self.db.last_spillere()
        self.assertEqual(
            self.mock_session_state.spilletid_df.at['Spiller1', 'Aktiv posisjon'],
            'Midtbane'
        )

    def test_perioder_ugyldig_data(self):
        """Tester håndtering av ugyldig periodedata"""
        self.mock_session_state.perioder = []
        self.db.lagre_perioder()
        self.db.last_perioder()
        self.assertEqual(self.mock_session_state.perioder, [])

if __name__ == '__main__':
    unittest.main()