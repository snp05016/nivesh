import json
import re
import multiprocessing
from typing import List, Dict, Any, Optional

from database import get_session
from services.llm_utils import deepseek_chat, HAIKU_MODEL
import anthropic
import os

def claude_haiku(messages: List[Dict[str, Any]]) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    client = anthropic.Anthropic(api_key=api_key)
    # Anthropic doesn't allow 'system' in the messages array, we have to extract it
    system_prompt = ""
    filtered_messages = []
    for m in messages:
        if m["role"] == "system":
            system_prompt += m["content"] + "\n"
        else:
            filtered_messages.append({"role": m["role"], "content": m["content"]})
    
    if not filtered_messages:
        filtered_messages.append({"role": "user", "content": "Hello"})
        
    response = client.messages.create(
        model=HAIKU_MODEL,
        system=system_prompt,
        max_tokens=2000,
        messages=filtered_messages
    )
    return response.content[0].text

def strip_emoji(text: str) -> str:
    """Strip emojis from text."""
    # Basic emoji removal regex
    return re.sub(r'[\U00010000-\U0010ffff]', '', text)

def _deep_analysis_worker(queue, ticker: str, exchange: str, user_id: int):
    """Worker process for deep analysis to protect the main thread."""
    from services.orchestrator import analyze
    import traceback
    try:
        # Run standard analysis
        result = analyze(ticker, exchange, user_id, deep_scan=False, scan_type="standard")
        queue.put({"status": "ok", "result": result})
    except Exception as e:
        queue.put({"status": "error", "error": str(e), "traceback": traceback.format_exc()})

def _manage_tokens(conversation_history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Summarize conversation if it gets too long, keeping system prompts and last 3 messages raw."""
    # Rough estimate: 1 token ~ 4 characters
    total_chars = sum(len(msg.get("content", "")) for msg in conversation_history if msg.get("role") != "system")
    
    if total_chars > 8000: # ~2000 tokens
        # We need to summarize
        recent_messages = conversation_history[-3:]
        older_messages = [m for m in conversation_history[:-3] if m.get("role") != "system"]
        system_messages = [m for m in conversation_history if m.get("role") == "system"]
        
        older_text = "\n".join([f"{m['role']}: {m['content']}" for m in older_messages])
        prompt = f"Summarize the following conversation history briefly:\n{older_text}"
        
        summary = deepseek_chat([{"role": "user", "content": prompt}])
        
        managed_history = system_messages + [
            {"role": "system", "content": f"Previous conversation summary: {summary}"}
        ] + recent_messages
        return managed_history
    return conversation_history

def process_copilot_request(user_message: str, conversation_history: List[Dict[str, Any]], current_context: Dict[str, Any], user_id: Optional[int]) -> Dict[str, Any]:
    """Process the chat request using LangGraph-like flow."""
    user_id = user_id or 0  # Default for unauthenticated users
    managed_history = _manage_tokens(conversation_history)
    
    # Inject system prompt with app navigation knowledge (kept outside token management)
    nav_context = current_context.get("app_navigation", "")
    system_prompt = {
        "role": "system",
        "content": f"You are the Nivesh AI Copilot, a helpful financial assistant that can discuss portfolio performance, analyze Indian stocks, explain market concepts, and guide users through the Nivesh app. When users ask where to find features, use the app navigation map below to provide clear directions (which tab, which section).\n\nAPP NAVIGATION MAP:\n{nav_context}"
    }
    managed_history = [system_prompt] + managed_history
    
    # 1. Intent Router (DeepSeek - Tier 1)
    context_str = json.dumps(current_context)
    intent_prompt = f"""
You are the Nivesh Financial Copilot Intent Router.
Given the user's message and current context, determine the intent.
Respond with EXACTLY ONE of the following words: GENERAL, PORTFOLIO, DEEP_ANALYSIS, or NAVIGATION.
If the user asks about their own holdings, performance, or portfolio, reply PORTFOLIO.
If the user asks for a deep analysis, buy/sell recommendation, or detailed research on a specific stock, reply DEEP_ANALYSIS.
If the user asks where to find something in the app, how to navigate, or what features exist, reply NAVIGATION.
Otherwise, reply GENERAL.

Context: {context_str}
User Message: {user_message}
"""
    intent = deepseek_chat([{"role": "user", "content": intent_prompt}]).strip().upper()
    
    reply = ""
    context_cards = None
    
    if "PORTFOLIO" in intent:
        # Query DB via get_session()
        with get_session() as db:
            from database import Portfolio
            holdings = db.query(Portfolio).filter(Portfolio.user_id == user_id).all()
            if holdings:
                holdings_str = ", ".join([f"{h.ticker} ({h.quantity} shares)" for h in holdings])
                prompt = f"The user has the following holdings: {holdings_str}. Answer their question: {user_message}"
            else:
                prompt = f"The user has no portfolio holdings currently. Answer their question: {user_message}"
                
            messages = managed_history + [{"role": "user", "content": prompt}]
            reply = claude_haiku(messages) # Tier 2 for synthesis
            
    elif "DEEP_ANALYSIS" in intent:
        # Extract ticker
        ticker_prompt = f"Extract the stock ticker symbol from this message and context. Context: {context_str}. Message: {user_message}. Return ONLY the ticker symbol (e.g. RELIANCE, HDFCBANK). If none found, reply NONE."
        ticker = deepseek_chat([{"role": "user", "content": ticker_prompt}]).strip().upper()
        
        if ticker == "NONE" or not ticker:
            messages = managed_history + [{"role": "user", "content": user_message}]
            reply = claude_haiku(messages)
        else:
            # Spawn multiprocessing
            q = multiprocessing.Queue()
            p = multiprocessing.Process(target=_deep_analysis_worker, args=(q, ticker, "NSE", user_id))
            p.start()
            # Wait for result with timeout
            try:
                res = q.get(timeout=60)
                p.join()
                
                if res["status"] == "ok":
                    analysis_data = res["result"]
                    signal = analysis_data.get("signal", "UNKNOWN")
                    # Prepare response
                    reply = f"I've analyzed {ticker}. The overall signal is {signal}."
                    context_cards = [analysis_data]
                else:
                    reply = f"I encountered an error analyzing {ticker}: {res.get('error')}"
            except Exception as e:
                p.terminate()
                reply = f"Analysis for {ticker} timed out or failed."
                
    elif "NAVIGATION" in intent:
        nav_context = current_context.get("app_navigation", "")
        nav_prompt = f"""You are a Nivesh app guide. Use ONLY the following app navigation map to answer the user's question about where to find features. Be concise and specific — tell them which tab, section, and how to reach it. If the feature they ask about is not listed, say so politely and suggest related features.

APP NAVIGATION MAP:
{nav_context}

User question: {user_message}"""
        reply = deepseek_chat([{"role": "user", "content": nav_prompt}])
        
    else: # GENERAL
        messages = managed_history + [{"role": "user", "content": f"Context: {context_str}\nMessage: {user_message}"}]
        reply = deepseek_chat(messages) # Fast response
        
    # Response Normalizer
    from main import _ban_western_scale
    reply = strip_emoji(reply)
    try:
        reply = _ban_western_scale(reply)
    except ValueError:
        # Retry with strict instruction
        messages = managed_history + [
            {"role": "user", "content": f"Context: {context_str}\nMessage: {user_message}"},
            {"role": "assistant", "content": reply},
            {"role": "user", "content": "Rewrite the previous response replacing any Millions/Billions/Trillions with Indian Numbering System (Lakhs/Crores)."}
        ]
        reply = claude_haiku(messages)
        reply = strip_emoji(reply)

    return {
        "reply": reply,
        "context_cards": context_cards
    }
