import json
from database import get_session, User, Portfolio
from routers.user import watchlist_get_endpoint

def test_watchlist():
    with get_session() as session:
        user = session.query(User).first()
        if not user:
            print("No users in db")
            return
            
        uid = user.id
        # Add test watchlist item
        item = session.query(Portfolio).filter_by(user_id=uid, ticker="ICICIBANK", group_name="watchlist").first()
        if not item:
            item = Portfolio(user_id=uid, ticker="ICICIBANK", company_name="ICICI Bank", group_name="watchlist", shares=0, buy_price=0)
            session.add(item)
            session.commit()

    # Need to pass authorization header but let's mock the token_user logic
    try:
        import routers.user
        routers.user.verify_access_token = lambda x: uid
        
        result = watchlist_get_endpoint(uid, "Bearer token")
        print("RESULT:")
        print(json.dumps(result, indent=2))
    except Exception as e:
        print("ERROR:", str(e))

if __name__ == "__main__":
    test_watchlist()
