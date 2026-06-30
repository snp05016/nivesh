import pytest
from decimal import Decimal
from datetime import date
from capital_gains_calculator import calculate_capital_gains, calculate_taxes, Transaction, AssetClass

def test_stcg_equity():
    transactions = [
        Transaction(
            asset_class=AssetClass.EQUITY,
            buy_date=date(2023, 4, 1),
            buy_price=Decimal("100.00"),
            buy_qty=100,
            sell_date=date(2023, 10, 1),
            sell_price=Decimal("150.00")
        )
    ]
    gains = calculate_capital_gains(transactions)
    assert gains["STCG"] == Decimal("5000.00")
    assert gains["LTCG"] == Decimal("0.00")

def test_ltcg_equity_no_grandfathering():
    transactions = [
        Transaction(
            asset_class=AssetClass.EQUITY,
            buy_date=date(2020, 4, 1),
            buy_price=Decimal("100.00"),
            buy_qty=100,
            sell_date=date(2023, 10, 1),
            sell_price=Decimal("150.00")
        )
    ]
    gains = calculate_capital_gains(transactions)
    assert gains["STCG"] == Decimal("0.00")
    assert gains["LTCG"] == Decimal("5000.00")

def test_ltcg_equity_grandfathering():
    # Buy Price: 100, FMV on 31 Jan 2018: 120, Sell Price: 150
    # Cost of acquisition = higher(100, lower(120, 150)) = higher(100, 120) = 120
    # Profit = 150 - 120 = 30 per share -> 3000
    transactions = [
        Transaction(
            asset_class=AssetClass.EQUITY,
            buy_date=date(2017, 4, 1),
            buy_price=Decimal("100.00"),
            buy_qty=100,
            sell_date=date(2023, 10, 1),
            sell_price=Decimal("150.00"),
            fmv_31_jan_2018=Decimal("120.00")
        )
    ]
    gains = calculate_capital_gains(transactions)
    assert gains["STCG"] == Decimal("0.00")
    assert gains["LTCG"] == Decimal("3000.00")

def test_ltcg_equity_grandfathering_loss():
    # Buy Price: 100, FMV on 31 Jan 2018: 120, Sell Price: 90
    # Cost of acquisition = higher(100, lower(120, 90)) = higher(100, 90) = 100
    # Loss = 90 - 100 = -10 per share -> -1000
    transactions = [
        Transaction(
            asset_class=AssetClass.EQUITY,
            buy_date=date(2017, 4, 1),
            buy_price=Decimal("100.00"),
            buy_qty=100,
            sell_date=date(2023, 10, 1),
            sell_price=Decimal("90.00"),
            fmv_31_jan_2018=Decimal("120.00")
        )
    ]
    gains = calculate_capital_gains(transactions)
    assert gains["STCG"] == Decimal("0.00")
    assert gains["LTCG"] == Decimal("-1000.00")

def test_tax_slabs_new_regime():
    # Example logic using 1.25L exemption and 12.5% LTCG, 20% STCG
    stcg = Decimal("10000.00")
    ltcg = Decimal("150000.00")
    taxes = calculate_taxes(stcg=stcg, ltcg=ltcg)
    
    # STCG tax = 10000 * 20% = 2000
    assert taxes["stcg_tax"] == Decimal("2000.00")
    
    # LTCG tax = (150000 - 125000) * 12.5% = 25000 * 0.125 = 3125.00
    assert taxes["ltcg_tax"] == Decimal("3125.00")
    assert taxes["total_tax"] == Decimal("5125.00")

def test_tax_slabs_ltcg_below_exemption():
    stcg = Decimal("10000.00")
    ltcg = Decimal("100000.00")
    taxes = calculate_taxes(stcg=stcg, ltcg=ltcg)
    
    # STCG tax = 10000 * 20% = 2000
    assert taxes["stcg_tax"] == Decimal("2000.00")
    
    # LTCG tax = 0 (since 100000 < 125000)
    assert taxes["ltcg_tax"] == Decimal("0.00")
    assert taxes["total_tax"] == Decimal("2000.00")
