"""Nivesh Lab: Time Machine simulator, trade autopsy, validation statistics and Trader School.

Everything here is pure and deterministic: no network, no database, no clock reads.
Data comes in through `lab.data.MarketData`; state is rebuilt by replaying an action log.
"""
