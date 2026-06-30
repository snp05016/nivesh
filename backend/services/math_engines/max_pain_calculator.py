def calculate_max_pain(options_chain):
    """
    Calculate max pain strike given an options chain.
    
    Args:
        options_chain (list of dict): List containing option chain data.
            Each dict should have: 'strike', 'call_oi', 'put_oi'
            
    Returns:
        float: Max pain strike price
    """
    if not options_chain:
        return 0.0

    strikes = sorted(list(set([opt['strike'] for opt in options_chain])))
    
    min_pain = float('inf')
    max_pain_strike = 0.0
    
    for test_strike in strikes:
        total_pain = 0.0
        
        for opt in options_chain:
            strike = opt['strike']
            
            # Calls expire in the money if underlying > strike
            if test_strike > strike:
                call_value = test_strike - strike
                total_pain += call_value * opt.get('call_oi', 0)
                
            # Puts expire in the money if underlying < strike
            if test_strike < strike:
                put_value = strike - test_strike
                total_pain += put_value * opt.get('put_oi', 0)
                
        if total_pain < min_pain:
            min_pain = total_pain
            max_pain_strike = test_strike
            
    return max_pain_strike
