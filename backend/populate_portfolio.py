import logging
"""
Populate saumya's portfolio with 50 diverse NSE stocks + trade journal history.
Dev databases only (it wipes that user's portfolio):
    ALLOW_DEV_SEED=1 python backend/populate_portfolio.py
"""
import sys, os, random, secrets
sys.path.insert(0, os.path.dirname(__file__))

from database import init_db, get_session, User, Portfolio, TradeJournal
from datetime import datetime, timedelta, timezone

# Top 50 diverse NSE stocks across all major sectors
STOCKS = [
    ("RELIANCE","Reliance Industries Ltd",2850,"Oil & Gas"),
    ("TCS","Tata Consultancy Services",3700,"IT"),
    ("HDFCBANK","HDFC Bank Ltd",1750,"Banking"),
    ("INFY","Infosys Ltd",1600,"IT"),
    ("ICICIBANK","ICICI Bank Ltd",1250,"Banking"),
    ("HINDUNILVR","Hindustan Unilever Ltd",2500,"FMCG"),
    ("ITC","ITC Ltd",480,"FMCG"),
    ("SBIN","State Bank of India",820,"Banking"),
    ("BHARTIARTL","Bharti Airtel Ltd",1450,"Telecom"),
    ("KOTAKBANK","Kotak Mahindra Bank",1900,"Banking"),
    ("LT","Larsen & Toubro Ltd",3600,"Infrastructure"),
    ("AXISBANK","Axis Bank Ltd",1150,"Banking"),
    ("BAJFINANCE","Bajaj Finance Ltd",7200,"NBFC"),
    ("ASIANPAINT","Asian Paints Ltd",3100,"Consumer"),
    ("MARUTI","Maruti Suzuki India Ltd",12800,"Auto"),
    ("SUNPHARMA","Sun Pharmaceutical Ind",1550,"Pharma"),
    ("TATAMOTORS","Tata Motors Ltd",980,"Auto"),
    ("ULTRACEMCO","UltraTech Cement Ltd",10500,"Cement"),
    ("NTPC","NTPC Ltd",360,"Power"),
    ("M&M","Mahindra & Mahindra",2800,"Auto"),
    ("TITAN","Titan Company Ltd",3500,"Consumer"),
    ("NESTLEIND","Nestle India Ltd",25000,"FMCG"),
    ("TATASTEEL","Tata Steel Ltd",165,"Steel"),
    ("JSWSTEEL","JSW Steel Ltd",880,"Steel"),
    ("ADANIENT","Adani Enterprises",3200,"Conglomerate"),
    ("ADANIPORTS","Adani Ports & SEZ",1400,"Infrastructure"),
    ("TECHM","Tech Mahindra Ltd",1400,"IT"),
    ("CIPLA","Cipla Ltd",1500,"Pharma"),
    ("DRREDDY","Dr Reddys Laboratories",6500,"Pharma"),
    ("COALINDIA","Coal India Ltd",480,"Mining"),
    ("DIVISLAB","Divis Laboratories",4500,"Pharma"),
    ("BRITANNIA","Britannia Industries",5400,"FMCG"),
    ("HEROMOTOCO","Hero MotoCorp",5200,"Auto"),
    ("HDFCLIFE","HDFC Life Insurance",650,"Insurance"),
    ("TATACONSUM","Tata Consumer Products",1100,"FMCG"),
    ("HINDALCO","Hindalco Industries",680,"Metals"),
    ("BPCL","Bharat Petroleum Corp",620,"Oil & Gas"),
    ("TRENT","Trent Ltd",5500,"Retail"),
    ("DLF","DLF Ltd",850,"Real Estate"),
    ("HAL","Hindustan Aeronautics",4500,"Defence"),
    ("ZOMATO","Zomato Ltd",250,"Consumer Tech"),
    ("VEDL","Vedanta Ltd",450,"Metals"),
    ("TATAPOWER","Tata Power",430,"Power"),
    ("DABUR","Dabur India",580,"FMCG"),
    ("HAVELLS","Havells India",1600,"Consumer Durables"),
    ("BEL","Bharat Electronics",300,"Defence"),
    ("POLYCAB","Polycab India",6500,"Cables"),
    ("APOLLOHOSP","Apollo Hospitals",6800,"Healthcare"),
    ("IRCTC","IRCTC Ltd",950,"Travel"),
    ("DMART","Avenue Supermarts",4500,"Retail"),
]

def main():
    if os.getenv("ALLOW_DEV_SEED") != "1":
        sys.exit("refusing: set ALLOW_DEV_SEED=1 (dev only)")
    init_db()
    with get_session() as session:
        saumya = session.query(User).filter(User.username == "saumya").first()
        if not saumya:
            from database import _hash_password
            password = secrets.token_urlsafe(12)
            saumya = User(username="saumya", password_hash=_hash_password(password), display_name="Saumya")
            session.add(saumya); session.commit(); session.refresh(saumya)
            print(f"Created dev user 'saumya' with password: {password}")
        logging.info(f"User: {saumya.username} (id={saumya.id})")

        existing = session.query(Portfolio).filter(Portfolio.user_id == saumya.id).delete()
        session.query(TradeJournal).filter(TradeJournal.user_id == saumya.id).delete()
        session.commit()
        logging.info(f"Cleared {existing} holdings + journal entries")

        added = 0
        for ticker, company, approx_price, sector in STOCKS:
            buy_price = round(approx_price * random.uniform(0.90, 1.06), 2)
            if buy_price > 10000: shares = random.randint(1, 15)
            elif buy_price > 1000: shares = random.randint(5, 80)
            elif buy_price > 100: shares = random.randint(20, 400)
            else: shares = random.randint(100, 1500)
            group = "holdings" if random.random() < 0.75 else "watchlist"
            session.add(Portfolio(user_id=saumya.id, ticker=ticker, company_name=company, shares=shares, buy_price=buy_price, group_name=group, notes=f"Mock. Sector: {sector}"))
            added += 1
        session.commit()
        logging.info(f"Added {added} stocks")

        holdings = session.query(Portfolio).filter(Portfolio.user_id == saumya.id, Portfolio.group_name == "holdings").all()
        actions, moods = ["BUY","SELL","HOLD","WATCH"], ["Confident","Cautious","Neutral","Bullish","Bearish"]
        reasons = [
            "Strong quarterly results — revenue up 15% YoY",
            "Technical breakout above 200 DMA with high volume",
            "Promoter buying detected — insider confidence signal",
            "Sector rotation — moving into defensives",
            "Valuation stretched — booking partial profits",
            "Adding on dips — long-term conviction",
            "Macro headwinds — reducing exposure",
            "New product launch catalyst — accumulating",
            "Peer analysis shows undervaluation vs competitors",
            "Stop-loss triggered — disciplined exit",
        ]
        jc = 0
        for holding in holdings:
            for _ in range(random.randint(2, 4)):
                days_ago = random.randint(1, 365)
                price_at_time = round(holding.buy_price * random.uniform(0.85, 1.15), 2)
                session.add(TradeJournal(user_id=saumya.id, ticker=holding.ticker, action=random.choice(actions), price_at_time=price_at_time, reason_text=random.choice(reasons), outcome_text=f"Position {'gained' if random.random()>0.5 else 'lost'} {random.uniform(1,20):.1f}%", company_name=holding.company_name, mood=random.choice(moods), created_at=datetime.now(timezone.utc) - timedelta(days=days_ago)))
                jc += 1
        session.commit()
        logging.info(f"Added {jc} journal entries")

        total = session.query(Portfolio).filter(Portfolio.user_id == saumya.id).count()
        hc = session.query(Portfolio).filter(Portfolio.user_id == saumya.id, Portfolio.group_name == "holdings").count()
        jt = session.query(TradeJournal).filter(TradeJournal.user_id == saumya.id).count()
        logging.info(f"Done: {total} stocks ({hc} holdings), {jt} journal entries")

if __name__ == "__main__":
    main()
