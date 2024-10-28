import streamlit as st
import pandas as pd
import numpy as np
import logging
from datetime import datetime
import os
from database import DatabaseHandler
import json

# Oppsett av logging
def setup_logging():
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    logg_filnavn = f'logs/fotballapp_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(logg_filnavn, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger(__name__)

logger = setup_logging()

# Legg til etter eksisterende imports
db = DatabaseHandler()

# Legg til i SessionState initialiseringen
if 'kamper' not in st.session_state:
    st.session_state.kamper = {}  # Dictionary med kampnavn som nøkkel

# I initialiseringen av session state (på toppen av filen)
if 'spillere' not in st.session_state:
    st.session_state.spillere = []  # eller en standardliste med spillere

# Legg til ny funksjon for å lagre kamp
def lagre_kampoppsett(navn, motstander):
    """Lagrer gjeldende kampoppsett"""
    try:
        # Konverter DataFrame til dict på en sikker måte
        spilletid_dict = {
            'data': st.session_state.spilletid_df.to_dict('split'),
            'index': st.session_state.spilletid_df.index.tolist(),
            'columns': st.session_state.spilletid_df.columns.tolist()
        }
        
        kamp_data = {
            'motstander': motstander,
            'dato': datetime.now().strftime("%Y-%m-%d"),
            'kamptid': st.session_state.kamptid,
            'perioder': st.session_state.perioder,
            'spilletid_df': spilletid_dict,
            'antall_paa_banen': st.session_state.antall_paa_banen
        }
        
        st.session_state.kamper[navn] = kamp_data
        
        # Lagre til fil
        with open('kamper.json', 'w', encoding='utf-8') as f:
            json.dump(st.session_state.kamper, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Kampoppsett lagret: {navn}")
        return True
    except Exception as e:
        logger.error(f"Feil ved lagring av kampoppsett: {str(e)}")
        return False

# Legg til funksjon for å laste kamp
def last_kampoppsett(navn):
    """Laster et tidligere kampoppsett"""
    try:
        if navn in st.session_state.kamper:
            kamp = st.session_state.kamper[navn]
            
            # Oppdater session state
            st.session_state.kamptid = kamp['kamptid']
            st.session_state.perioder = kamp['perioder']
            st.session_state.antall_paa_banen = kamp.get('antall_paa_banen', 9)  # Default til 9 hvis ikke funnet
            
            # Gjenopprett DataFrame
            spilletid_dict = kamp['spilletid_df']
            df = pd.DataFrame(**spilletid_dict['data'])
            df.index = spilletid_dict['index']
            df.columns = spilletid_dict['columns']
            
            # Oppdater spilletid_df
            st.session_state.spilletid_df = df
            
            # Oppdater kamp_info
            st.session_state.kamp_info['motstander'] = kamp['motstander']
            st.session_state.kamp_info['dato'] = kamp['dato']
            
            logger.info(f"Kampoppsett lastet: {navn}")
            return True
    except Exception as e:
        logger.error(f"Feil ved lasting av kampoppsett: {str(e)}")
    return False

# Forenklet initialisering av session state
def initialize_session_state():
    if 'kamp_info' not in st.session_state:
        st.session_state.kamp_info = {
            'motstander': '',
            'dato': datetime.now().strftime("%Y-%m-%d")
        }
    
    if 'spilletid_df' not in st.session_state:
        logger.info("Initialiserer ny session state")
        # Standard spillerliste som utgangspunkt
        spillere = {
            'Susanne': 'Keeper',
            'Tuva': 'Midtstopper',
            'Adele': 'Back',
            'Sarah': 'Back',
            'Madelen': 'Sentral midtbane',
            'Ingrid': 'Sentral midtbane',
            'Karen': 'Spiss',
            'Diyana': 'Ving',
            'Martine': 'Back',
            'Hanna': 'Back',
            'Veslemøy': 'Ving',
            'Emilie': 'Ving',
            'Lilly': 'Ving'
        }
        
        # Opprett DataFrame
        df = pd.DataFrame(index=spillere.keys())
        df['Posisjoner'] = pd.Series({navn: [pos] for navn, pos in spillere.items()})
        df['Aktiv posisjon'] = pd.Series(spillere)
        df['Tilgjengelig'] = True
        df['Total spilletid'] = 0
        df['Differanse'] = 0
        df['Mål spilletid'] = 0
        
        # Legg til periodekolonner
        perioder = generer_perioder(st.session_state.get('kamptid', 80))
        for periode in perioder:
            df[periode] = False
        
        st.session_state.spilletid_df = df
        logger.info(f"Opprettet ny spilletid_df med {len(spillere)} spillere")
    
    if 'antall_paa_banen' not in st.session_state:
        st.session_state.antall_paa_banen = 9
        
    if 'kamptid' not in st.session_state:
        st.session_state.kamptid = 80
        
    if 'perioder' not in st.session_state:
        st.session_state.perioder = generer_perioder(st.session_state.kamptid)
    
    db.last_alt()

def generer_perioder(total_tid):
    """Genererer bytteperioder basert på total kamptid"""
    perioder = []
    omgang_tid = total_tid // 2
    
    # Første omgang
    tid = 0
    perioder.append(f'0-15')  # Første periode er alltid 15 min
    tid += 15
    while tid < omgang_tid:
        neste_tid = min(tid + 10, omgang_tid)
        perioder.append(f'{tid}-{neste_tid}')
        tid = neste_tid
        
    # Andre omgang
    tid = omgang_tid
    while tid < total_tid:
        neste_tid = min(tid + 10, total_tid)
        perioder.append(f'{tid}-{neste_tid}')
        tid = neste_tid
    
    return perioder

def oppdater_perioder():
    logger.info(f"Oppdaterer perioder for kamptid {st.session_state.kamptid} minutter")
    nye_perioder = generer_perioder(st.session_state.kamptid)
    gamle_perioder = [col for col in st.session_state.spilletid_df.columns if '-' in col]
    
    # Fjern gamle periodekolonner
    st.session_state.spilletid_df = st.session_state.spilletid_df.drop(columns=gamle_perioder)
    
    # Legg til nye periodekolonner med False som standardverdi
    for periode in nye_perioder:
        st.session_state.spilletid_df[periode] = False
    
    st.session_state.perioder = nye_perioder
    logger.info(f"Nye perioder generert: {nye_perioder}")

def kalkuler_spilletid(df, perioder):
    logger.debug("Starter kalkulering av spilletid")
    total_spilletid = 0
    
    for periode in perioder:
        start, slutt = map(int, periode.split('-'))
        varighet = slutt - start
        total_spilletid += df[periode].astype(int) * varighet
    
    df['Total spilletid'] = total_spilletid
    df['Differanse'] = df['Total spilletid'] - df['Mål spilletid']
    logger.info(f"Total spilletid kalkulert. Gjennomsnitt: {df['Total spilletid'].mean():.1f} minutter")
    return df

def telle_spillere_pa_banen(df, periode):
    """
    Teller antall spillere på banen i en gitt periode og returnerer detaljert info.
    
    Args:
        df (pd.DataFrame): Spillerdataframe
        periode (str): Perioden som skal telles
    
    Returns:
        tuple: (antall, liste med spillere)
    """
    spillere_pa_banen = df[df[periode] == True]
    return len(spillere_pa_banen), spillere_pa_banen.index.tolist()

def oppdater_mal_spilletid():
    """Oppdaterer mål spilletid basert på kamptid og antall tilgjengelige spillere"""
    df = st.session_state.spilletid_df
    tilgjengelige_spillere = df[df['Tilgjengelig']].shape[0]
    if tilgjengelige_spillere > 0:
        gjennomsnittlig_tid = (st.session_state.kamptid * st.session_state.antall_paa_banen) / tilgjengelige_spillere
        df.loc[df['Tilgjengelig'], 'Mål spilletid'] = round(gjennomsnittlig_tid)
    return df

def generer_kamprapport(df, perioder):
    """Genererer en detaljert kamprapport med bytter, oppstillinger og benk"""
    rapport = []
    forrige_periode_spillere = set()
    
    for periode in perioder:
        periode_spillere = set(df[df[periode] == True].index)
        tilgjengelige_spillere = set(df[df['Tilgjengelig'] == True].index)
        spillere_pa_benk = tilgjengelige_spillere - periode_spillere
        
        inn = periode_spillere - forrige_periode_spillere
        ut = forrige_periode_spillere - periode_spillere
        
        rapport.append(f"\nPeriode {periode}")
        rapport.append("-" * 40)
        
        if inn:
            rapport.append("Inn:")
            for spiller in sorted(inn):
                pos = df.at[spiller, 'Aktiv posisjon']
                rapport.append(f"- {spiller} ({pos})")
        
        if ut:
            rapport.append("\nUt:")
            for spiller in sorted(ut):
                pos = df.at[spiller, 'Aktiv posisjon']
                rapport.append(f"- {spiller} ({pos})")
        
        rapport.append("\nPå banen:")
        for spiller in sorted(periode_spillere):
            pos = df.at[spiller, 'Aktiv posisjon']
            rapport.append(f"- {spiller} ({pos})")
            
        rapport.append("\nPå benken:")
        for spiller in sorted(spillere_pa_benk):
            pos = df.at[spiller, 'Aktiv posisjon']
            rapport.append(f"- {spiller} ({pos})")
        
        forrige_periode_spillere = periode_spillere
    
    return "\n".join(rapport)

def propager_valg(df, periode_index, perioder, original_spiller):
    try:
        current_periode = perioder[periode_index]
        
        # Finn midtpunktet basert på kamptid
        kamptid = st.session_state.kamptid
        halvtid_tid = kamptid // 2
        
        # Finn halvtid_idx ved å telle perioder til vi når halvtid
        halvtid_idx = 0
        for i, periode in enumerate(perioder):
            slutt_tid = int(periode.split('-')[1])
            if slutt_tid >= halvtid_tid:
                halvtid_idx = i
                break
        
        # Legg til debugging logging
        logger.info(f"Alle perioder: {perioder}")
        logger.info(f"Total antall perioder: {len(perioder)}")
        logger.info(f"Halvtid tid: {halvtid_tid} minutter")
        logger.info(f"Halvtid index: {halvtid_idx}")
        logger.info(f"Nåværende periode index: {periode_index}")
        
        # Bestem hvilken omgang vi er i og sett grenser
        if periode_index < halvtid_idx:
            # Første omgang - inkluder alle perioder frem til halvtid
            start_idx = periode_index + 1
            slutt_idx = halvtid_idx + 1  # Legg til +1 for å inkludere siste periode i omgangen
            logger.info(f"Første omgang: propagerer fra indeks {start_idx} til {slutt_idx}")
            logger.info(f"Dette inkluderer periodene: {perioder[start_idx:slutt_idx]}")
        else:
            # Andre omgang
            start_idx = periode_index + 1
            slutt_idx = len(perioder)
            logger.info(f"Andre omgang: propagerer fra indeks {start_idx} til {slutt_idx}")
            logger.info(f"Dette inkluderer periodene: {perioder[start_idx:slutt_idx]}")
        
        valgt_status = df.at[original_spiller, current_periode]
        logger.info(f"Starter propagering for {original_spiller} fra periode {current_periode} (index {periode_index})")
        logger.info(f"Perioder som skal propageres: {perioder[start_idx:slutt_idx]}")
        
        # Propager til alle etterfølgende perioder i samme omgang
        for i in range(start_idx, slutt_idx):
            neste_periode = perioder[i]
            antall_pa_banen, spillere = telle_spillere_pa_banen(df, neste_periode)
            
            logger.info(f"Vurderer periode {neste_periode}: {antall_pa_banen} spillere på banen")
            
            # Hvis vi setter på spiller, sjekk at det er plass
            if valgt_status and antall_pa_banen >= st.session_state.antall_paa_banen and not df.at[original_spiller, neste_periode]:
                logger.info(f"Stopper propagering i periode {neste_periode} - for mange spillere")
                break
            
            # Oppdater status
            gammel_status = df.at[original_spiller, neste_periode]
            df.at[original_spiller, neste_periode] = valgt_status
            logger.info(f"Oppdaterte {original_spiller} i periode {neste_periode}: {gammel_status} -> {valgt_status}")
        
        logger.info(f"Fullførte propagering for {original_spiller}")
        return df
        
    except Exception as e:
        logger.error(f"Feil ved propagering av valg: {str(e)}", exc_info=True)
        return df

def valider_bytte(df, periode, ny_spiller, gammel_status, ny_status):
    """
    Validerer om et bytte er tillatt basert på antall spillere på banen.
    """
    try:
        current_count = df[periode].sum()
        
        if gammel_status and not ny_status:  # Tar av en spiller
            return True
        elif not gammel_status and ny_status:  # Setter på en spiller
            if current_count >= st.session_state.antall_paa_banen:
                return False
        return True
    except Exception as e:
        logger.error(f"Feil ved validering av bytte: {str(e)}")
        return False

def format_spillere_i_posisjon(spillere_per_posisjon, posisjoner):
    """
    Helper funksjon for å formatere spillerliste.
    Håndterer nå spillere med flere posisjoner ved å kun vise dem i deres aktive posisjon.
    """
    if isinstance(posisjoner, str):
        posisjoner = [posisjoner]
    
    # Hold styr på allerede viste spillere
    viste_spillere = set()
    spillere = []
    
    for pos, spiller_liste in spillere_per_posisjon.items():
        if any(p in pos for p in posisjoner):
            for spiller in spiller_liste:
                if spiller not in viste_spillere:
                    spillere.append(spiller)
                    viste_spillere.add(spiller)
    
    return ', '.join(sorted(spillere)) if spillere else '-'

def generer_formasjon(spillere_per_posisjon):
    """
    Helper funksjon for å generere formasjonsstreng.
    Oppdatert for å kun telle spillere basert på deres aktive posisjon.
    """
    forsvar = sum(1 for pos, spillere in spillere_per_posisjon.items() 
                 if any(p in pos for p in ['Back', 'Midtstopper']))
    
    midtbane = sum(1 for pos, spillere in spillere_per_posisjon.items() 
                  if any(p in pos for p in ['Sentral midtbane', 'Ving']))
    
    angrep = sum(1 for pos, spillere in spillere_per_posisjon.items() 
                if 'Spiss' in pos)
    
    return f"{forsvar}-{midtbane}-{angrep}"

def generer_detaljert_kampoppsett(df, perioder):
    """
    Genererer et detaljert kampoppsett som viser bytter, formasjoner, spillere på banen og benk.
    """
    kampoppsett_data = []
    forrige_spillere = set()
    
    for periode in perioder:
        # Finn spillere på banen i denne perioden
        spillere_i_periode = set(df[df[periode] == True].index)
        tilgjengelige_spillere = set(df[df['Tilgjengelig'] == True].index)
        spillere_pa_benk = tilgjengelige_spillere - spillere_i_periode
        
        # Beregn bytter
        inn = spillere_i_periode - forrige_spillere
        ut = forrige_spillere - spillere_i_periode
        
        # Organiser spillere etter deres aktive posisjon
        spillere_per_posisjon = {}
        for spiller in spillere_i_periode:
            aktiv_posisjon = df.at[spiller, 'Aktiv posisjon']
            if aktiv_posisjon not in spillere_per_posisjon:
                spillere_per_posisjon[aktiv_posisjon] = []
            spillere_per_posisjon[aktiv_posisjon].append(spiller)
        
        # Formater formasjon basert på aktive posisjoner
        formasjon = generer_formasjon(spillere_per_posisjon)
        
        kampoppsett_data.append({
            'Periode': periode,
            'Formasjon': formasjon,
            'Bytter Inn': ', '.join(sorted(inn)) if inn else '-',
            'Bytter Ut': ', '.join(sorted(ut)) if ut else '-',
            'Keeper': format_spillere_i_posisjon(spillere_per_posisjon, 'Keeper'),
            'Forsvar': format_spillere_i_posisjon(spillere_per_posisjon, ['Back', 'Midtstopper']),
            'Midtbane': format_spillere_i_posisjon(spillere_per_posisjon, ['Sentral midtbane', 'Ving']),
            'Angrep': format_spillere_i_posisjon(spillere_per_posisjon, ['Spiss']),
            'På benken': ', '.join(sorted(spillere_pa_benk)) if spillere_pa_benk else '-'
        })
        
        forrige_spillere = spillere_i_periode
    
    return pd.DataFrame(kampoppsett_data)

def get_max_spillere_per_posisjon(posisjon):
    """
    Returnerer maksimalt antall spillere tillatt i hver posisjon basert på formasjon.
    """
    max_spillere = {
        'Keeper': 1,
        'Back': 4,        # Økt til 4 for å tillate både høyre og venstre back
        'Midtstopper': 2,
        'Sentral midtbane': 2,
        'Ving': 4,        # Økt til 4 for å tillate både høyre og venstre ving
        'Spiss': 2        # Økt til 2 for mer fleksibilitet
    }
    return max_spillere.get(posisjon, 2)  # Standard 2 hvis ukjent posisjon

def valider_bytte_med_posisjoner(df, periode, ny_spiller, gammel_status, ny_status):
    """
    Validerer bytter - returnerer bare True/False og posisjon.
    """
    try:
        antall_pa_banen, spillere = telle_spillere_pa_banen(df, periode)
        maks_spillere = st.session_state.antall_paa_banen
        
        # Logger situasjonen (beholder logging for debugging)
        logger.info(f"""
            Validerer bytte i periode {periode}:
            - Spiller: {ny_spiller}
            - Nåværende status: {'på' if gammel_status else 'av'} banen
            - Ønsket status: {'på' if ny_status else 'av'} banen
            - Antall på banen: {antall_pa_banen}/{maks_spillere}
            - Spillere på banen: {', '.join(spillere)}
        """)

        # Håndter utbytte (tar av spiller)
        if gammel_status and not ny_status:
            return True, None

        # Håndter innbytte (setter på spiller)
        elif not gammel_status and ny_status:
            # Sjekk om laget er fullt
            if antall_pa_banen >= maks_spillere:
                return False, None

            # Hvis det er plass, tillat bytte med aktiv posisjon
            return True, df.at[ny_spiller, 'Aktiv posisjon']

        return True, None

    except Exception as e:
        logger.error(f"Feil ved validering av bytte: {str(e)}", exc_info=True)
        return False, None

def oppdater_spillerposisjon(df, spiller, periode, ny_posisjon):
    """
    Oppdaterer spillerens posisjon for en spesifikk periode.
    """
    if f'posisjon_{periode}' not in df.columns:
        df[f'posisjon_{periode}'] = df['Aktiv posisjon']
    df.at[spiller, f'posisjon_{periode}'] = ny_posisjon
    return df

def main():
    logger.info("Starter applikasjon")
    
    st.title("⚽ Fotball Kampplanlegger")
    
    initialize_session_state()
    
    # Sidebar for kampinfo og innstillinger
    with st.sidebar:
        st.header("Kampinformasjon")
        
        # Enkel kampinfo
        st.session_state.kamp_info['motstander'] = st.text_input(
            "Motstander",
            value=st.session_state.kamp_info['motstander']
        )
        st.session_state.kamp_info['dato'] = st.date_input(
            "Kampdato",
            value=datetime.strptime(st.session_state.kamp_info['dato'], "%Y-%m-%d")
        ).strftime("%Y-%m-%d")
        
        st.markdown("---")
        
        # Kampinnstillinger
        st.header("Kampinnstillinger")
        
        ny_kamptid = st.number_input(
            "Total kamptid (minutter)",
            min_value=40,
            max_value=120,
            value=st.session_state.kamptid,
            step=5
        )
        
        if ny_kamptid != st.session_state.kamptid:
            st.session_state.kamptid = ny_kamptid
            oppdater_perioder()
        
        ny_antall_paa_banen = st.number_input(
            "Antall spillere på banen",
            value=st.session_state.antall_paa_banen,
            min_value=7,
            max_value=11
        )
        
        if ny_antall_paa_banen != st.session_state.antall_paa_banen:
            st.session_state.antall_paa_banen = ny_antall_paa_banen
            oppdater_mal_spilletid()
        
        # Vis total tilgjengelig spilletid
        total_tilgjengelig_tid = st.session_state.kamptid * st.session_state.antall_paa_banen
        st.info(f"Total tilgjengelig spilletid: {total_tilgjengelig_tid} minutter")

    # Oppdater mål spilletid før visning
    st.session_state.spilletid_df = oppdater_mal_spilletid()
    
        # Hovedområde
    st.header("Kampplanlegging")
    
    # Del opp perioder i omganger
    halvtid_idx = len(st.session_state.perioder) // 2
    perioder_omgang1 = st.session_state.perioder[:halvtid_idx]
    perioder_omgang2 = st.session_state.perioder[halvtid_idx:]
    
    # Vis bare tilgjengelige spillere
    edited_df = st.session_state.spilletid_df[st.session_state.spilletid_df['Tilgjengelig']].copy()
    
    col1, col2 = st.columns(2)
    
    # Første og andre omgang
    for omgang, perioder in [("Første omgang", perioder_omgang1), ("Andre omgang", perioder_omgang2)]:
        with col1 if omgang == "Første omgang" else col2:
            st.subheader(omgang)
            
            # Fjern "Velg alle" knapper og erstatt med enkel periode-header
            cols_header = st.columns([3] + [1] * len(perioder))
            with cols_header[0]:
                st.write("**Periode**")
            
            for i, periode in enumerate(perioder, 1):
                with cols_header[i]:
                    st.write(periode)

            # Vis spillere og deres checkboxer
            for spiller_idx, spiller_row in edited_df.iterrows():
                cols_spillere = st.columns([3] + [1] * len(perioder))
                with cols_spillere[0]:
                    aktiv_pos = spiller_row['Aktiv posisjon']
                    alle_pos = ', '.join(spiller_row['Posisjoner'])
                    st.write(f"{spiller_idx} ({aktiv_pos})")
                    st.caption(f"Kan spille: {alle_pos}")
                
                # Håndter hver periode for spilleren
                for i, periode in enumerate(perioder):
                    with cols_spillere[i + 1]:
                        # Sjekk først om byttet ville være gyldig
                        antall_pa_banen, _ = telle_spillere_pa_banen(edited_df, periode)
                        kan_settes_pa = (antall_pa_banen < st.session_state.antall_paa_banen) or edited_df.at[spiller_idx, periode]
                        
                        # Opprett checkbox
                        ny_status = st.checkbox(
                            "På banen",
                            value=edited_df.at[spiller_idx, periode],
                            key=f"{periode}_{spiller_idx}",
                            label_visibility="collapsed",
                            disabled=not kan_settes_pa and not edited_df.at[spiller_idx, periode]
                        )
                        
                        # Hvis status endres, valider og oppdater
                        if ny_status != edited_df.at[spiller_idx, periode]:
                            if ny_status and antall_pa_banen >= st.session_state.antall_paa_banen:
                                # Ikke tillat endringen hvis det blir for mange spillere
                                continue
                            edited_df.at[spiller_idx, periode] = ny_status
                            periode_index = perioder.index(periode)
                            edited_df = propager_valg(edited_df, periode_index, perioder, spiller_idx)

    # Oppdater beregninger
    edited_df = kalkuler_spilletid(edited_df, st.session_state.perioder)
    
    # Validering og oversikt
    st.header("Oversikt og validering")
    
    # Total spilletidsvalidering
    total_spilletid = edited_df['Total spilletid'].sum()
    total_tilgjengelig_tid = st.session_state.kamptid * st.session_state.antall_paa_banen
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total spilletid brukt", total_spilletid)
    with col2:
        st.metric("Total tilgjengelig spilletid", total_tilgjengelig_tid)
    
    if total_spilletid != total_tilgjengelig_tid:
        st.warning(f"Total spilletid ({total_spilletid} min) samsvarer ikke med tilgjengelig spilletid ({total_tilgjengelig_tid} min)")
    else:
        st.success("Total spilletid samsvarer med tilgjengelig spilletid")
    
    # Vis spilletidsoversikt
    st.subheader("Spilletidsoversikt")
    oversikt_df = edited_df[['Total spilletid', 'Mål spilletid', 'Differanse']].copy()
    st.dataframe(oversikt_df)
    
    # Vis status for hver periode
    st.subheader("Periodestatus")
    # Sjekk at det finnes perioder før vi lager kolonner
    if st.session_state.perioder and len(st.session_state.perioder) > 0:
        status_cols = st.columns(len(st.session_state.perioder))
        
        for i, periode in enumerate(st.session_state.perioder):
            with status_cols[i]:
                spillere_pa_banen, _ = telle_spillere_pa_banen(edited_df, periode)
                st.metric(
                    periode,
                    spillere_pa_banen,
                    spillere_pa_banen - st.session_state.antall_paa_banen
                )
    else:
        st.warning("Ingen perioder er definert ennå")
    
    st.session_state.spilletid_df.update(edited_df)
    
    # Legg til kamprapport-seksjon
    st.header("Kamprapport")
    if st.button("Generer kamprapport"):
        logger.info("Genererer kamprapport")
        rapport = generer_kamprapport(edited_df, st.session_state.perioder)
        logger.debug(f"Kamprapport generert:\n{rapport}")
        st.text_area("Kampplan", rapport, height=400)
        
        # Last ned rapport som tekstfil
        st.download_button(
            label="Last ned kamprapport",
            data=rapport,
            file_name="kamprapport.txt",
            mime="text/plain"
        )

    # Erstatt den eksisterende kampoppsett-seksjonen med:
    st.header("Detaljert Kampoppsett")
    
    # Generer detaljert kampoppsett
    detaljert_oppsett = generer_detaljert_kampoppsett(edited_df, st.session_state.perioder)
    
    # Vis som ekspanderbar tabell for hver periode
    for _, rad in detaljert_oppsett.iterrows():
        with st.expander(f"Periode {rad['Periode']} - {rad['Formasjon']}"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.write("**Bytter:**")
                st.write(f"Inn: {rad['Bytter Inn']}")
                st.write(f"Ut: {rad['Bytter Ut']}")
            
            with col2:
                st.write("**Formasjon:**")
                st.write(f"Keeper: {rad['Keeper']}")
                st.write(f"Forsvar: {rad['Forsvar']}")
                st.write(f"Midtbane: {rad['Midtbane']}")
                st.write(f"Angrep: {rad['Angrep']}")
            
            with col3:
                st.write("**På benken:**")
                st.write(f"På benken: {rad['På benken']}")
    
    # Vis også som samlet tabell
    st.subheader("Komplett Kampplan")
    st.dataframe(detaljert_oppsett, use_container_width=True)
    
    # Last ned kampplan som CSV
    csv = detaljert_oppsett.to_csv(index=False)
    st.download_button(
        label="Last ned kampplan som CSV",
        data=csv,
        file_name="kampplan.csv",
        mime="text/csv"
    )

    # I sidebar, oppdater lagre/laste-seksjonen:
    with st.sidebar:
        with st.expander("Lagre/Last kampoppsett"):
            col1, col2 = st.columns(2)
            
            with col1:
                kamp_navn = st.text_input("Navn på kamp")
                if st.button("Lagre kampoppsett") and kamp_navn:
                    if lagre_kampoppsett(kamp_navn, st.session_state.kamp_info['motstander']):
                        st.success(f"Kampoppsett lagret: {kamp_navn}")
                    else:
                        st.error("Kunne ikke lagre kampoppsettet")
            
            with col2:
                if st.session_state.kamper:
                    valgt_kamp = st.selectbox(
                        "Velg tidligere kampoppsett",
                        options=list(st.session_state.kamper.keys())
                    )
                    if st.button("Last kampoppsett"):
                        if last_kampoppsett(valgt_kamp):
                            st.rerun()  # Oppdater siden for å vise endringene
                        else:
                            st.error("Kunne ikke laste kampoppsettet")

    # I hovedområdet, etter at endringer er gjort:
    if edited_df is not None:
        st.session_state.spilletid_df.update(edited_df)
        db.lagre_alt()  # Lagre til database
        
        # Hvis det finnes et aktivt kampnavn, oppdater også kampoppsettet
        if 'aktivt_kamp_navn' in st.session_state and st.session_state.aktivt_kamp_navn:
            lagre_kampoppsett(st.session_state.aktivt_kamp_navn, st.session_state.kamp_info['motstander'])

if __name__ == "__main__":
    main()
