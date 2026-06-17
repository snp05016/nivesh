import asyncio
import logging
import io
import sys
import os
from datetime import datetime, timezone

import pandas as pd
import requests
import yfinance as yf

# Ensure we can import from backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_session
from models.db_models import StockUniverse

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Fallback: full NSE universe (~170 tickers) for when NSE CSV is blocked
FALLBACK_TICKERS = [
    # NIFTY 50 — Large Cap
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BAJFINANCE.NS", "BHARTIARTL.NS",
    "KOTAKBANK.NS", "AXISBANK.NS", "ASIANPAINT.NS", "MARUTI.NS", "SUNPHARMA.NS",
    "TITAN.NS", "ULTRACEMCO.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS",
    "ONGC.NS", "POWERGRID.NS", "NTPC.NS", "COALINDIA.NS", "JSWSTEEL.NS",
    "TATASTEEL.NS", "HINDALCO.NS", "GRASIM.NS", "ADANIENT.NS", "ADANIPORTS.NS",
    "BAJAJ-AUTO.NS", "BAJAJFINSV.NS", "BPCL.NS", "BRITANNIA.NS", "CIPLA.NS",
    "DIVISLAB.NS", "DRREDDY.NS", "EICHERMOT.NS", "HDFCLIFE.NS", "HEROMOTOCO.NS",
    "INDUSINDBK.NS", "LT.NS", "M&M.NS", "NESTLEIND.NS", "SBILIFE.NS",
    "SHRIRAMFIN.NS", "TATACONSUM.NS", "TATAMOTORS.NS", "TRENT.NS", "UPL.NS",
    # NIFTY Next 50 / Upper Mid Cap
    "ADANIGREEN.NS", "ADANITRANS.NS", "AMBUJACEM.NS", "APOLLOHOSP.NS", "BANDHANBNK.NS",
    "BIOCON.NS", "BOSCHLTD.NS", "CANBK.NS", "CHOLAFIN.NS", "COLPAL.NS",
    "CONCOR.NS", "DABUR.NS", "DLF.NS", "FEDERALBNK.NS", "GAIL.NS",
    "GODREJCP.NS", "HAVELLS.NS", "IDFCFIRSTB.NS", "INDUSTOWER.NS", "IOC.NS",
    "IRCTC.NS", "LTIM.NS", "LUPIN.NS", "MUTHOOTFIN.NS", "NAUKRI.NS",
    "PAGEIND.NS", "PGHH.NS", "PIDILITIND.NS", "PIIND.NS", "PNB.NS",
    "SBICARD.NS", "SIEMENS.NS", "SRF.NS", "TORNTPHARM.NS", "TVSMOTOR.NS",
    "VEDL.NS", "VOLTAS.NS", "ZOMATO.NS", "PAYTM.NS",
    # Mid Cap — Banking & Finance
    "AUBANK.NS", "CITYUNIONB.NS", "EQUITASBNK.NS", "KARURVYSYA.NS", "LICHSGFIN.NS",
    "MANAPPURAM.NS", "RBLBANK.NS", "SOUTHBANK.NS", "YESBANK.NS",
    # Mid Cap — IT & Tech
    "COFORGE.NS", "KPITTECH.NS", "MPHASIS.NS", "PERSISTENT.NS", "TATAELXSI.NS",
    # Mid Cap — Pharma & Healthcare
    "ALKEM.NS", "AUROPHARMA.NS", "GLENMARK.NS", "IPCA.NS", "LAURUSLABS.NS",
    "NATCOPHARM.NS", "ZYDUSLIFE.NS",
    # Mid Cap — Consumer & FMCG
    "EMAMILTD.NS", "GODREJIND.NS", "MARICO.NS", "VBL.NS",
    # Mid Cap — Auto & Ancillary
    "APOLLOTYRE.NS", "ASHOKLEY.NS", "BALKRISIND.NS", "BHARATFORG.NS",
    "MOTHERSON.NS", "SONACOMS.NS",
    # Mid Cap — Infrastructure & Engineering
    "ABB.NS", "BEL.NS", "BHEL.NS", "CUMMINSIND.NS", "HAL.NS", "IRFC.NS",
    "POLYCAB.NS", "THERMAX.NS",
    # Mid Cap — Metals & Materials
    "JINDALSTEL.NS", "NMDC.NS", "SAIL.NS",
    # Mid Cap — Cement & Real Estate
    "ACC.NS", "DALMIABHA.NS", "GODREJPROP.NS", "OBEROIRLTY.NS", "RAMCOCEM.NS",
    # Small Cap
    "AARTIIND.NS", "ASTRAL.NS", "CDSL.NS", "DEEPAKNTR.NS", "GESHIP.NS",
    "HINDCOPPER.NS", "ICICIGI.NS", "INDHOTEL.NS", "IRCON.NS", "JUBLFOOD.NS",
    "LICI.NS", "MAXHEALTH.NS", "MCX.NS", "RECLTD.NS", "TEJASNET.NS",
    "VARUNBEV.NS",
    # ── Batch 2: More Nifty Next 50 / F&O ──
    "ABBOTINDIA.NS", "ALKEM.NS", "ATGL.NS", "BANKBARODA.NS", "BERGEPAINT.NS",
    "CAMS.NS", "COROMANDEL.NS", "CROMPTON.NS", "DIXON.NS", "DMART.NS",
    "FORTIS.NS", "GODREJPROP.NS", "GUJGASLTD.NS", "HONAUT.NS", "ICICIPRULI.NS",
    "JINDALSTEL.NS", "JKCEMENT.NS", "JSWENERGY.NS", "LICHSGFIN.NS", "LODHA.NS",
    # ── Mid Cap — Consumer & Retail ──
    "ABBOTINDIA.NS", "BATAINDIA.NS", "BBTC.NS", "CERA.NS", "CHAMBLFERT.NS",
    "BBTC.NS", "BIKAJI.NS", "CROMPTON.NS", "DARSHANORNA.NS", "DEVYANI.NS",
    "DMART.NS", "FINOLEXIND.NS", "GODREJAGRO.NS", "GREENLAM.NS", "GREENPLY.NS",
    "HLEGLAS.NS", "JYOTHYLAB.NS", "KAJARIACER.NS", "KALYANKJIL.NS", "KANSAINER.NS",
    "NYKAA.NS", "POLICYBZR.NS", "PRESTIGE.NS", "RADICO.NS", "RAJESHEXPO.NS",
    "RAYMOND.NS", "RESTAURANT.NS", "SHOPPERS.NS", "SKFINDIA.NS", "SPICEJET.NS",
    "STAR.NS", "SYMPHONY.NS", "TATACOFFEE.NS", "TITAGARH.NS", "UNITEDBNK.NS",
    "VGUARD.NS", "VSTIND.NS", "WELSPUNIND.NS", "WESTLIFE.NS", "WHIRLPOOL.NS",
    "ZYDUSWELL.NS",
    # ── Mid Cap — Chemicals & Fertilizers ──
    "AARTISURF.NS", "ALKEM.NS", "ALKILAMINE.NS", "ANURAS.NS", "ATFL.NS",
    "BALAMINES.NS", "BASF.NS", "BEPL.NS", "CHAMBLFERT.NS", "CLEAN.NS",
    "COROMANDEL.NS", "DEEPAKFERT.NS", "FINEORG.NS", "FLUOROCHEM.NS", "GALAXYSURF.NS",
    "GNFC.NS", "GRSE.NS", "GSFC.NS", "HIKAL.NS", "JBCHEPHARM.NS",
    "JUBILANT.NS", "NAVINFLUOR.NS", "NEULANDLAB.NS", "ORIENTCEM.NS", "RALLIS.NS",
    "SOLARINDS.NS", "TATACHEM.NS", "UPL.NS", "VINATIORGA.NS", "VISHNU.NS",
    # ── Mid Cap — Logistics & Transport ──
    "AEGISLOG.NS", "ALLCARGO.NS", "BLUEDART.NS", "CONCOR.NS", "DELHIVERY.NS",
    "GATI.NS", "MAHLOGISTICS.NS", "TCI.NS", "TCIEXP.NS", "TRANSPORT.NS",
    "VRLLOG.NS",
    # ── Mid Cap — Media & Entertainment ──
    "DISHTV.NS", "DTIL.NS", "HATHWAY.NS", "INOXLEISUR.NS", "JAGRAN.NS",
    "NAZARA.NS", "NETWORK18.NS", "PVRINOX.NS", "SAREGAMA.NS", "SUNTV.NS",
    "TIPSINDLTD.NS", "TVTODAY.NS", "ZEEL.NS", "ZEELEARN.NS", "ZOMATO.NS",
    # ── Small Cap — IT & Tech ──
    "AFFLE.NS", "BIRLASOFT.NS", "BSOFT.NS", "CYIENT.NS", "DATAPATTNS.NS",
    "ECLERX.NS", "EKI.NS", "FIRSTSOURCE.NS", "HAPPSTMNDS.NS", "INFIBEAM.NS",
    "INTELLECT.NS", "IRCTC.NS", "KEC.NS", "KEI.NS", "LAURUSLABS.NS",
    "MASTEK.NS", "MINDA.NS", "MTARTECH.NS", "NUCLEUS.NS", "OFSS.NS",
    "QUICKHEAL.NS", "RATEGAIN.NS", "ROUTE.NS", "SONATSOFTW.NS", "SUBROS.NS",
    "TANLA.NS", "TATACOMM.NS", "TCS.NS", "ZENSARTECH.NS",
    # ── Small Cap — Banks & NBFC ──
    "AUBANK.NS", "BANDHANBNK.NS", "CAMS.NS", "CAPLIPOINT.NS", "CHOLAFIN.NS",
    "CRISIL.NS", "CSBBANK.NS", "DCBBANK.NS", "EDELWEISS.NS", "FUSION.NS",
    "HOMEFIRST.NS", "ICHITRA.NS", "IDFC.NS", "IIFL.NS", "INDIANB.NS",
    "INDIASHL.NS", "JMFINANCIL.NS", "KARVY.NS", "L&TFH.NS", "MOTILALOFS.NS",
    "MUTHOOT.NS", "NIPPONAMF.NS", "PNBHOUSING.NS", "SHAREINDIA.NS", "SPANDAN.NS",
    "UCOBANK.NS", "UNIONBANK.NS", "UTIAMC.NS",
    # ── Small Cap — Pharma & Healthcare ──
    "AJANTPHARM.NS", "AMIORG.NS", "APOLLOHOSP.NS", "ASTERDM.NS", "ERIS.NS",
    "GLAND.NS", "GRANULES.NS", "INDRAMEDCO.NS", "JBMA.NS", "KIMSPRIME.NS",
    "KRISHNA.NS", "LALPATHLAB.NS", "MEDPLUS.NS", "METROPOLIS.NS", "NARAYANHRU.NS",
    "POLYMED.NS", "SHILPAMED.NS", "STAR.NS", "SUDARSHAN.NS", "TASTYBITE.NS",
    "THYROCARE.NS", "UNIVASTU.NS", "VIMTA.NS",
    # ── Small Cap — Manufacturing & Engineering ──
    "ADORWELD.NS", "AIAENG.NS", "BEML.NS", "BLS.NS", "CARBORUNIV.NS",
    "CGPOWER.NS", "COCHINSHIP.NS", "ELECON.NS", "FINCABLES.NS", "GMMPFAUDLR.NS",
    "GRINDWELL.NS", "HARSHA.NS", "HEG.NS", "HLEGLAS.NS", "IFGLREFRAC.NS",
    "INGERRAND.NS", "JWL.NS", "KIRLOSENG.NS", "LAXMIMACH.NS", "MAZDOCK.NS",
    "PRAJIND.NS", "RHI.NS", "SANGHI.NS", "SANSERA.NS", "SCHAEFFLER.NS",
    "SHANTIGEAR.NS", "STLTECH.NS", "TIMKEN.NS", "TITAGARH.NS", "TRITURBINE.NS",
    "VOLTAMP.NS", "WELCORP.NS",
    # ── Small Cap — Consumer Durables, Retail ──
    "AMBER.NS", "BORORENEW.NS", "CARTRADE.NS", "CERA.NS", "DIXON.NS",
    "ELECTCAST.NS", "FINEOTEX.NS", "FLAIR.NS", "GANESHHOUC.NS", "HINDWARE.NS",
    "KAJARIACER.NS", "KALYANKJIL.NS", "KIRIINDUS.NS", "LAOPALA.NS", "LUXIND.NS",
    "MALLCOM.NS", "MANYAVAR.NS", "MIRZAINT.NS", "NILKAMAL.NS", "PGIL.NS",
    "PRINCEPIPE.NS", "RUPA.NS", "SAFARI.NS", "SUPREMEIND.NS", "TTKPRESTIG.NS",
    # ── Small Cap — Agri, Food, Dairy ──
    "APEXFROZ.NS", "AVANTIFEED.NS", "BALRAMCHIN.NS", "BPCL.NS", "BRITISHFOOD.NS",
    "CCL.NS", "DPABHUSHAN.NS", "DWARKESH.NS", "FDC.NS", "GODFREYPG.NS",
    "GRMOVER.NS", "ITC.NS", "JUBLFOOD.NS", "KRBL.NS", "MAHSEAMLES.NS",
    "MANGLMCEM.NS", "MILTON.NS", "MOTHERSON.NS", "NAUKRI.NS", "NESTLEIND.NS",
    "PARAGMILK.NS", "PATANJALI.NS", "PRABHAT.NS", "RADHIKAJEW.NS", "RAMCOIND.NS",
    "SADBHAV.NS", "SENCO.NS", "SMSPHARMA.NS", "SULA.NS", "TASTYBITE.NS",
    "TATACOFFEE.NS", "UJJIVAN.NS", "VENKYS.NS", "VIKASLIFE.NS", "VSTTILLERS.NS",
    "WARBURG.NS", "WELENT.NS",
    # ── Small Cap — Real Estate, Infra, Power ──
    "ACE.NS", "ASHIANA.NS", "BRIGADE.NS", "DBREALTY.NS", "ECLERX.NS",
    "GANESH.NS", "GMRINFRA.NS", "HEMIPROP.NS", "INFRATEL.NS", "JMC.NS",
    "KNRCON.NS", "KOLTEPATIL.NS", "MACPOWER.NS", "MAHINDCIE.NS", "MAHLIFE.NS",
    "NESCO.NS", "OBEROIRLTY.NS", "PNCINFRA.NS", "POWERGRID.NS", "PURVA.NS",
    "RATEGAIN.NS", "RPPINFRA.NS", "SOBHA.NS", "SUNTECK.NS", "SUPREME.NS",
    "TEXRAIL.NS", "VASCONEQ.NS",
    # ── Small Cap — Textiles ──
    "ALOKTEXT.NS", "AMBICACO.NS", "ARVIND.NS", "FILTRA.NS", "GRASIM.NS",
    "HIMATSEIDE.NS", "INTEGRA.NS", "KPRMILL.NS", "LOYAL.NS", "MAYURUNIQ.NS",
    "NAHARSP.NS", "NITINSPIN.NS", "SANGAM.NS", "SRF.NS", "SUTLEJTEX.NS",
    "TRIDENT.NS", "VARDMANTEX.NS", "WELSPUNLIV.NS", "ZODIACLOTH.NS",
    # ── Misc / Diversified ──
    "360ONE.NS", "3MINDIA.NS", "AAVAS.NS", "AEGISCHEM.NS", "AETHER.NS",
    "ANGELONE.NS", "ANUPAM.NS", "APOLLOTYRE.NS", "APTECHT.NS", "ASTRAMICRO.NS",
    "BECTORFOOD.NS", "CANFINHOME.NS", "CASTROLIND.NS", "CCL.NS", "CENTURYPLY.NS",
    "CESC.NS", "CHALET.NS", "CHOLAHLDNG.NS", "COALINDIA.NS", "COMPINFO.NS",
    "CPSEETF.NS", "CREDITACC.NS", "CYBERTECH.NS", "DATAPATTNS.NS", "DCMSHRIRAM.NS",
    "DYNAMATECH.NS", "ECLERX.NS", "ELGIEQUIP.NS", "EMAMIPAP.NS", "ENGINERSIN.NS",
    "EPL.NS", "EQUITASBNK.NS", "EUREKA.NS", "FCL.NS", "FINOPB.NS",
    "FORCEMOT.NS", "GABRIEL.NS", "GALAXYSURF.NS", "GARFIBRES.NS", "GENUSPOWER.NS",
    "GILLETTE.NS", "GLS.NS", "GPPL.NS", "GRAPHITE.NS", "GRAVITA.NS",
    "GUJALKALI.NS", "GUJFLUORO.NS", "HAPPSTMNDS.NS", "HARIOMPIPE.NS", "HEIDELBERG.NS",
    "HERITGFOOD.NS", "HFCL.NS", "HINDZINC.NS", "HITACHI.NS", "HONDAPOWER.NS",
    "HUHTAMAKI.NS", "ICRA.NS", "IFBIND.NS", "IGL.NS", "IMFA.NS",
    "INDIAGLYCO.NS", "INOXGREEN.NS", "IONEXCHANG.NS", "ISEC.NS", "ITDCEM.NS",
    "JAMNAAUTO.NS", "JAYSREETEA.NS", "JBCHEPHARM.NS", "JCHAC.NS", "JKIL.NS",
    "JKLAKSHMI.NS", "JKPAPER.NS", "JSL.NS", "JTLIND.NS", "JUBLINGREA.NS",
    "JUSTDIAL.NS", "KABRAEXTRU.NS", "KALPATPOWR.NS", "KANORICHEM.NS", "KEI.NS",
    "KIRLOSBROS.NS", "KITES.NS", "KNRCON.NS", "KOPRAN.NS", "KRBL.NS",
    "KRSNAA.NS", "KSB.NS", "LATENTVIEW.NS", "LEMONTREE.NS", "LINCOLN.NS",
    "LLOYDSME.NS", "LTFOODS.NS", "MAHABANK.NS", "MANINFRA.NS", "MARATHON.NS",
    "MASFIN.NS", "MATRIMONY.NS", "MAWANASUG.NS", "MINDACORP.NS", "MMTC.NS",
    "MOL.NS", "MONTECARLO.NS", "MOREPENLAB.NS", "MOSCHIP.NS", "MPSLTD.NS",
    "MRPL.NS", "MSPL.NS", "MTARTECH.NS", "NACLIND.NS", "NATCOPHARM.NS",
    "NCLIND.NS", "NDL.NS", "NDTV.NS", "NEWGEN.NS", "NH.NS",
    "NIITLTD.NS", "NILKAMAL.NS", "NLCINDIA.NS", "NMDC.NS", "NOCIL.NS",
    "NTPC.NS", "NUCLEUS.NS", "OIL.NS", "OILCOUNTUB.NS", "ONGC.NS",
    "ORIENTELEC.NS", "PAGEIND.NS", "PAISALO.NS", "PANACEABIO.NS", "PARAS.NS",
    "PATELENG.NS", "PCBL.NS", "PDSL.NS", "PETRONET.NS", "PGHH.NS",
    "PHOENIXLTD.NS", "PNBGILTS.NS", "POONAWALLA.NS", "POWERGRID.NS", "PPL.NS",
    "PRABHAT.NS", "PRECWIRE.NS", "PRICOLLTD.NS", "PRINCEPIPE.NS", "PRSMJOHNSN.NS",
    "PTC.NS", "PURVA.NS", "QUESS.NS", "RALLIS.NS", "RAMCOCEM.NS",
    "RANEENGINE.NS", "RATNAMANI.NS", "REDINGTON.NS", "RELAXO.NS", "REPCOHOME.NS",
    "RIIL.NS", "ROLEXRINGS.NS", "ROSSARI.NS", "RTNPOWER.NS", "RVNL.NS",
    "SAGCEM.NS", "SALZERELEC.NS", "SANDHAR.NS", "SANGHIIND.NS", "SANOFI.NS",
    "SARDAEN.NS", "SATINDLTD.NS", "SCHNEIDER.NS", "SESHAPAPER.NS", "SFL.NS",
    "SHARDACROP.NS", "SHEMAROO.NS", "SHYAMMETL.NS", "SIGACHI.NS", "SIS.NS",
    "SJS.NS", "SKMEGGPROD.NS", "SOBHA.NS", "SOLARA.NS", "SONATSOFTW.NS",
    "SPAL.NS", "SPECTRUM.NS", "SPICEJET.NS", "SREINFRA.NS", "SUNCLAY.NS",
    "SUPRAJIT.NS", "SUPREME.NS", "SURYAROSNI.NS", "SUVENPHAR.NS", "SWARAJENG.NS",
    "SYNGENE.NS", "TAINWALCHM.NS", "TARSONS.NS", "TATAPOWER.NS", "TCNSBRANDS.NS",
    "TEGA.NS", "THANGAMAYL.NS", "THERMAX.NS", "TIMETECHNO.NS", "TINPLATE.NS",
    "TIPSINDLTD.NS", "TRIVENI.NS", "TTKPRESTIG.NS", "TVSMOTOR.NS", "UNIONBANK.NS",
    "UJJIVANSFB.NS", "UTIAMC.NS", "VAKRANGEE.NS", "VALIANT.NS", "VASCONEQ.NS",
    "VBL.NS", "VENUSPIPES.NS", "VESUVIUS.NS", "VIJAYA.NS", "VIKASECO.NS",
    "VINATIORGA.NS", "VIPIND.NS", "VISAKAIND.NS", "VISHWARAJ.NS", "VMART.NS",
    "WABCOINDIA.NS", "WELSPUNIND.NS", "WENDT.NS", "WESTLIFE.NS", "WOCKPHARMA.NS",
    "YESBANK.NS", "ZFCVINDIA.NS", "ZYDUSLIFE.NS",
]

def fetch_nse_symbols() -> list[str]:
    """Fetch all NSE listed symbols from NSE India website."""
    url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
    }
    try:
        logger.info(f"Fetching NSE equity list from {url}...")
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        df = pd.read_csv(io.StringIO(response.text))
        symbols = df['SYMBOL'].tolist()
        
        # Suffix with .NS for Yahoo Finance
        tickers = [f"{sym}.NS" for sym in symbols]
        logger.info(f"Successfully fetched {len(tickers)} tickers from NSE.")
        return tickers
    except Exception as e:
        logger.error(f"Failed to fetch from NSE: {e}. Using fallback.")
        return FALLBACK_TICKERS

async def fetch_ticker_info(ticker: str, semaphore: asyncio.Semaphore) -> tuple[str, dict]:
    """Fetch stock info from yfinance asynchronously."""
    async with semaphore:
        try:
            # Run yfinance blocking call in a thread
            info = await asyncio.to_thread(lambda: yf.Ticker(ticker).info)
            # small sleep to prevent rate limits
            await asyncio.sleep(0.1)
            return ticker, info
        except Exception as e:
            logger.debug(f"Failed to fetch {ticker}: {e}")
            return ticker, {}

def parse_float(val) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None

async def populate_universe():
    with get_session() as session:
        existing_tickers = {r[0] for r in session.query(StockUniverse.ticker).all()}
    
    tickers = fetch_nse_symbols()
    # Filter out tickers we already have
    tickers_to_fetch = [t for t in tickers if t not in existing_tickers]
    
    # Limit to remainings needed to reach ~2000 or process the rest
    # We will just process up to 1000 at a time to avoid rate limits
    tickers_to_fetch = tickers_to_fetch[:1000]
    
    if not tickers_to_fetch:
        logger.info("All stocks already populated.")
        return
        
    logger.info(f"Starting to fetch yfinance data for {len(tickers_to_fetch)} remaining stocks...")

    # Lower concurrency to help prevent rate limits
    semaphore = asyncio.Semaphore(5)
    
    tasks = [fetch_ticker_info(t, semaphore) for t in tickers_to_fetch]
    results = await asyncio.gather(*tasks)

    # Process and save to database
    records = []
    for t, info in results:
        if not info or "shortName" not in info:
            continue
            
        market_cap = parse_float(info.get("marketCap"))
        pe_ratio = parse_float(info.get("trailingPE"))
        
        # Convert ratios to percentages where needed
        roe = parse_float(info.get("returnOnEquity"))
        roe = roe * 100 if roe is not None else None
        
        roce = parse_float(info.get("returnOnCapitalEmployed")) # Sometimes missing in YF, but we try
        roce = roce * 100 if roce is not None else None
        
        promoter = parse_float(info.get("heldPercentInsiders"))
        promoter = promoter * 100 if promoter is not None else None
        
        fii_holding = parse_float(info.get("heldPercentInstitutions"))
        fii_holding = fii_holding * 100 if fii_holding is not None else None
        
        div_yield = parse_float(info.get("dividendYield"))
        div_yield = div_yield * 100 if div_yield is not None else None
        
        ebitda_margin = parse_float(info.get("ebitdaMargins"))
        ebitda_margin = ebitda_margin * 100 if ebitda_margin is not None else None
        
        # Convert yf debtToEquity ratio (YF provides it as a percentage e.g., 50.5 for 50.5% or ratio, varies, but usually percentage in info)
        # We will keep it as ratio if we divide by 100 (standard Nivesh approach in nl_screener)
        de = parse_float(info.get("debtToEquity"))
        if de is not None:
            de = de / 100.0  # Convert 50.5 to 0.505 ratio
        
        stock_record = StockUniverse(
            ticker=t,
            company_name=info.get("shortName", t),
            sector=info.get("sector", "Unknown"),
            industry=info.get("industry", "Unknown"),
            market_cap=market_cap,
            pe_ratio=pe_ratio,
            roe=roe,
            roce=roce,
            debt_to_equity=de,
            promoter_holding=promoter,
            fii_holding=fii_holding,
            dii_holding=None, # YF doesn't split FII and DII clearly
            dividend_yield=div_yield,
            ebitda_margin=ebitda_margin,
            price_change_3m=None, # Require historical data fetch, omitted for speed
            price_change_1y=None, 
            rsi=None,
            updated_at=datetime.now(timezone.utc)
        )
        records.append(stock_record)
        
    logger.info(f"Successfully processed {len(records)} valid stock records. Saving to database...")
    
    # Deduplicate by ticker — bulk_save_objects fails on UNIQUE constraint if batch has dupes
    seen_tickers = set()
    deduped = []
    for r in records:
        if r.ticker not in seen_tickers:
            seen_tickers.add(r.ticker)
            deduped.append(r)
    records = deduped
    
    with get_session() as session:
        # Do not delete, just append the new ones
        session.bulk_save_objects(records)
        session.commit()
        
    logger.info("Stock universe updated successfully!")

if __name__ == "__main__":
    asyncio.run(populate_universe())
