import streamlit as st
import requests
import xml.etree.ElementTree as ET
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

ECB_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"

st.set_page_config(
    page_title="Schweizer Notarkostenrechner",
    page_icon="🇨🇭",
    layout="centered",
)

def money(value: Decimal) -> str:
    q = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    s = f"{q:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")

@st.cache_data(ttl=3600)
def get_ecb_chf_rate():
    headers = {"User-Agent": "Mozilla/5.0 Notarkostenrechner/1.0"}
    response = requests.get(ECB_URL, headers=headers, timeout=10)
    response.raise_for_status()

    root = ET.fromstring(response.content)

    date_node = None
    chf_rate = None

    for elem in root.iter():
        if elem.tag.endswith("Cube") and "time" in elem.attrib:
            date_node = elem.attrib["time"]
        if elem.tag.endswith("Cube") and elem.attrib.get("currency") == "CHF":
            chf_rate = elem.attrib.get("rate")

    if not date_node or not chf_rate:
        raise RuntimeError("Der CHF-Referenzkurs konnte in den EZB-Daten nicht gefunden werden.")

    return Decimal(chf_rate), date_node

def parse_german_number(text: str) -> Decimal:
    text = text.strip().replace(" ", "")
    if not text:
        raise InvalidOperation

    # Deutsche Eingaben wie 1.234.567,89
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    # Englische Dezimalzahl wie 1234.56 oder reine Ganzzahl bleibt unverändert.
    return Decimal(text)

def calculate(eur_value: Decimal, rate: Decimal):
    chf_value = eur_value * rate
    fee_025 = chf_value * Decimal("0.0025")
    fee_factor = fee_025 * Decimal("1.5")
    minimum_applies = fee_factor < Decimal("500")
    fee_chf = max(fee_factor, Decimal("500"))
    fee_eur = fee_chf / rate

    return {
        "eur_value": eur_value,
        "rate": rate,
        "chf_value": chf_value,
        "fee_025": fee_025,
        "fee_factor": fee_factor,
        "minimum_applies": minimum_applies,
        "fee_chf": fee_chf,
        "fee_eur": fee_eur,
    }

st.title("Schweizer Notarkostenrechner")
st.caption("Berechnung auf Grundlage des zuletzt veröffentlichten EZB-Referenzkurses EUR/CHF")

try:
    rate, rate_date = get_ecb_chf_rate()
    st.success(f"EZB-Referenzkurs vom {rate_date}: 1 EUR = {rate} CHF")
except Exception as exc:
    st.error(
        "Der EZB-Referenzkurs konnte derzeit nicht automatisch geladen werden. "
        "Bitte versuchen Sie es später erneut."
    )
    with st.expander("Technische Fehlermeldung"):
        st.code(str(exc))
    st.stop()

with st.form("calculation_form"):
    eur_input = st.text_input(
        "Bemessungswert in EUR",
        value="1.000.000,00",
        help="Beispiel: 1.000.000,00",
    )
    submitted = st.form_submit_button("Berechnen", use_container_width=True)

if submitted:
    try:
        eur_value = parse_german_number(eur_input)
        if eur_value <= 0:
            st.error("Bitte geben Sie einen Betrag größer als 0 EUR ein.")
            st.stop()

        r = calculate(eur_value, rate)

        st.divider()
        st.subheader("Berechnungsschritte")

        st.markdown(
            f"""
**1. Bemessungswert in EUR**  
{money(r['eur_value'])} EUR

**2. Umrechnung in CHF**  
{money(r['eur_value'])} EUR × {r['rate']} CHF/EUR  
= **{money(r['chf_value'])} CHF**

**3. Berechnung von 0,25 %**  
{money(r['chf_value'])} CHF × 0,25 %  
= **{money(r['fee_025'])} CHF**

**4. Multiplikation mit dem Faktor 1,5**  
{money(r['fee_025'])} CHF × 1,5  
= **{money(r['fee_factor'])} CHF**
"""
        )

        if r["minimum_applies"]:
            st.markdown(
                f"""
**5. Prüfung des Mindestbetrags von 500 CHF**  
Berechneter Betrag: {money(r['fee_factor'])} CHF  
Mindestbetrag: 500,00 CHF  
→ Der Mindestbetrag ist anzusetzen.

**Ergebnis in CHF: {money(r['fee_chf'])} CHF**
"""
            )
        else:
            st.markdown(
                f"""
**5. Prüfung des Mindestbetrags von 500 CHF**  
Berechneter Betrag: {money(r['fee_factor'])} CHF  
Mindestbetrag: 500,00 CHF  
→ Der Mindestbetrag greift nicht.

**Ergebnis in CHF: {money(r['fee_chf'])} CHF**
"""
            )

        st.markdown(
            f"""
**6. Rückrechnung in EUR**  
{money(r['fee_chf'])} CHF ÷ {r['rate']} CHF/EUR  
= **{money(r['fee_eur'])} EUR**
"""
        )

        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Notarkosten in CHF", f"{money(r['fee_chf'])} CHF")
        with col2:
            st.metric("Notarkosten in EUR", f"{money(r['fee_eur'])} EUR")

        st.info(
            f"Verwendeter Wechselkurs: EZB-Referenzkurs vom {rate_date}, "
            f"1 EUR = {rate} CHF."
        )

st.divider()
st.caption(
    "Hinweis: Die EZB veröffentlicht Referenzkurse grundsätzlich an Geschäftstagen. "
    "Verwendet wird jeweils der zuletzt veröffentlichte EUR/CHF-Referenzkurs. "
    "Die EZB weist darauf hin, dass ihre Referenzkurse Informationszwecken dienen."
)
