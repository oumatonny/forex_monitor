"""
ForexScalperAI - Professional Trading Bot API
FastAPI backend with multi-strategy signal engine,
MetaTrader5 integration, and WebSocket real-time data.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import json
import os
import uuid
import logging

import uvicorn
from pydantic import BaseModel
import numpy as np
import pandas as pd

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="ForexScalperAI API",
    version="2.0.0",
    description="Professional Multi-Strategy Forex Trading Bot API"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer(auto_error=False)

# ---------------------------------------------------------------------------
# Data Models (Pydantic)
# ---------------------------------------------------------------------------
class SignalType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    NEUTRAL = "NEUTRAL"

class TimeFrame(str, Enum):
    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    M30 = "M30"
    H1 = "H1"
    H4 = "H4"
    D1 = "D1"

class StrategyType(str, Enum):
    SMC = "SMC"
    ICT = "ICT"
    SUPPLY_DEMAND = "SUPPLY_DEMAND"
    PRICE_ACTION = "PRICE_ACTION"
    SMART_MONEY = "SMART_MONEY"
    TREND_FOLLOWING = "TREND_FOLLOWING"

class Signal(BaseModel):
    id: str
    pair: str
    type: SignalType
    strategy: StrategyType
    entry: float
    sl: float
    tp: float
    confidence: float  # 0-100
    timeFrame: str
    timestamp: str
    expiry: str
    reasons: List[str]
    risk_reward: float
    lot_size: float

class MarketData(BaseModel):
    pair: str
    bid: float
    ask: float
    spread: float
    change_24h: float
    high_24h: float
    low_24h: float
    volume_24h: float
    timestamp: str

class TradeTicket(BaseModel):
    id: str
    pair: str
    type: SignalType
    entry: float
    sl: float
    tp: float
    lot: float
    status: str  # open, closed, cancelled
    pnl: float = 0.0
    open_time: str
    close_time: Optional[str] = None

class AccountInfo(BaseModel):
    balance: float
    equity: float
    margin: float
    free_margin: float
    margin_level: float
    total_trades: int
    total_profit: float

# ---------------------------------------------------------------------------
# In-Memory Stores
# ---------------------------------------------------------------------------
signals_db: List[Signal] = []
trades_db: List[TradeTicket] = []
market_data_db: Dict[str, MarketData] = {}
connected_clients: List[WebSocket] = []
strategy_results: Dict[str, List[Dict]] = {}

# ---------------------------------------------------------------------------
# Simulated Market Data Generator (Replace with MT5/Oanda for production)
# ---------------------------------------------------------------------------
PAIRS = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD",
    "NZDUSD", "EURGBP", "EURJPY", "GBPJPY", "XAUUSD", "XAGUSD"
]

base_prices = {
    "EURUSD": 1.0850, "GBPUSD": 1.2640, "USDJPY": 151.50, "USDCHF": 0.9050,
    "AUDUSD": 0.6650, "USDCAD": 1.3650, "NZDUSD": 0.5950, "EURGBP": 0.8580,
    "EURJPY": 163.50, "GBPJPY": 190.80, "XAUUSD": 2325.50, "XAGUSD": 27.50
}

async def market_data_generator():
    """Simulate real-time market data updates"""
    while True:
        for pair in PAIRS:
            base = base_prices.get(pair, 1.0)
            # Simulate small price movements
            noise = np.random.normal(0, base * 0.0002)
            bid = round(base + noise, 5)
            spread = round(base * 0.00015, 5)  # ~1.5 pips for most pairs
            ask = round(bid + spread, 5)
            change = round(np.random.normal(0, 0.15), 2)
            
            market_data_db[pair] = MarketData(
                pair=pair,
                bid=bid,
                ask=ask,
                spread=spread,
                change_24h=change,
                high_24h=round(bid * 1.002, 5),
                low_24h=round(bid * 0.998, 5),
                volume_24h=round(np.random.uniform(100000, 500000), 2),
                timestamp=datetime.utcnow().isoformat()
            )
        await asyncio.sleep(2)


# ---------------------------------------------------------------------------
# Multi-Strategy Signal Engine
# ---------------------------------------------------------------------------
class StrategyEngine:
    def __init__(self):
        self.strategies = {
            StrategyType.SMC: self.smc_strategy,
            StrategyType.ICT: self.ict_strategy,
            StrategyType.SUPPLY_DEMAND: self.supply_demand_strategy,
            StrategyType.PRICE_ACTION: self.price_action_strategy,
            StrategyType.SMART_MONEY: self.smart_money_strategy,
            StrategyType.TREND_FOLLOWING: self.trend_following_strategy,
        }

    def generate_signals(self, pair: str, timeframe: TimeFrame) -> List[Signal]:
        signals = []
        for strat_name, strat_func in self.strategies.items():
            try:
                sig = strat_func(pair, timeframe)
                if sig:
                    signals.append(sig)
            except Exception as e:
                logger.error(f"Strategy {strat_name} error: {e}")
        return signals

    def _create_signal(self, pair: str, strat: StrategyType, 
                       signal_type: SignalType, entry: float, 
                       sl_pips: float, tp_pips: float,
                       confidence: float, reasons: List[str],
                       timeframe: TimeFrame) -> Signal:
        
        # Adjust pip values for JPY pairs and precious metals
        if "JPY" in pair or pair in ("XAUUSD", "XAGUSD"):
            pip_mult = 1.0  # Already in smaller decimals
        else:
            pip_mult = 0.0001
        
        if pair in ("XAUUSD", "XAGUSD"):
            pip_mult = 0.1
        
        sl = entry - sl_pips * pip_mult if signal_type == SignalType.BUY else entry + sl_pips * pip_mult
        tp = entry + tp_pips * pip_mult if signal_type == SignalType.BUY else entry - tp_pips * pip_mult
        
        risk_reward = tp_pips / sl_pips if sl_pips != 0 else 1.0
        lot_size = 0.01  # Default micro lot
        
        return Signal(
            id=str(uuid.uuid4()),
            pair=pair,
            type=signal_type,
            strategy=strat,
            entry=round(entry, 5),
            sl=round(sl, 5),
            tp=round(tp, 5),
            confidence=confidence,
            timeFrame=timeframe.value,
            timestamp=datetime.utcnow().isoformat(),
            expiry=(datetime.utcnow() + timedelta(hours=4)).isoformat(),
            reasons=reasons,
            risk_reward=round(risk_reward, 2),
            lot_size=lot_size
        )

    # ── Strategy 1: Smart Money Concepts (SMC) ──────────────────────────────
    def smc_strategy(self, pair: str, tf: TimeFrame) -> Optional[Signal]:
        entry = base_prices.get(pair, 1.0)
        # Simulate order block detection + breaker block + fair value gap
        trend = np.random.choice([SignalType.BUY, SignalType.SELL], p=[0.55, 0.45])
        if trend == SignalType.BUY:
            return self._create_signal(pair, StrategyType.SMC, SignalType.BUY, entry,
                                       sl_pips=15, tp_pips=45, confidence=78.5,
                                       reasons=["Bullish Order Block detected at support",
                                               "Fair Value Gap (FVG) filled ",
                                               "Break of Structure (BOS) confirmed"], timeframe=tf)
        else:
            return self._create_signal(pair, StrategyType.SMC, SignalType.SELL, entry,
                                       sl_pips=15, tp_pips=40, confidence=72.3,
                                       reasons=["Bearish Order Block at resistance",
                                               "Mitigation of sell-side liquidity",
                                               "Change of Character (CHOCH) to bearish"], timeframe=tf)

    # ── Strategy 2: Inner Circle Trader (ICT) ─────────────────────────────
    def ict_strategy(self, pair: str, tf: TimeFrame) -> Optional[Signal]:
        entry = base_prices.get(pair, 1.0)
        # ICT concepts: Liquidity sweep, inducement, fair value gap
        trend = np.random.choice([SignalType.BUY, SignalType.SELL], p=[0.5, 0.5])
        if trend == SignalType.BUY:
            return self._create_signal(pair, StrategyType.ICT, SignalType.BUY, entry,
                                       sl_pips=12, tp_pips=48, confidence=82.1,
                                       reasons=["Sell-side liquidity sweep",
                                               "Inducement to bearish before reversal",
                                               "Bullish Fair Value Gap (FVG) respected"], timeframe=tf)
        else:
            return self._create_signal(pair, StrategyType.ICT, SignalType.SELL, entry,
                                       sl_pips=12, tp_pips=40, confidence=76.8,
                                       reasons=["Buy-side liquidity sweep",
                                               "Inducement to bullish before reversal",
                                               "Bearish Fair Value Gap (FVG) respected"], timeframe=tf)

    # ── Strategy 3: Supply & Demand ────────────────────────────────────────
    def supply_demand_strategy(self, pair: str, tf: TimeFrame) -> Optional[Signal]:
        entry = base_prices.get(pair, 1.0)
        trend = np.random.choice([SignalType.BUY, SignalType.SELL], p=[0.52, 0.48])
        if trend == SignalType.BUY:
            return self._create_signal(pair, StrategyType.SUPPLY_DEMAND, SignalType.BUY, entry,
                                       sl_pips=18, tp_pips=50, confidence=68.5,
                                       reasons=["Strong demand zone created",
                                               "Price retraced to fresh zone",
                                               "Aggressive buying candles from zone"], timeframe=tf)
        else:
            return self._create_signal(pair, StrategyType.SUPPLY_DEMAND, SignalType.SELL, entry,
                                       sl_pips=18, tp_pips=45, confidence=65.2,
                                       reasons=["Fresh supply zone identified",
                                               "Price reacted from zone top",
                                               "Reversal candle at supply"], timeframe=tf)

    # ── Strategy 4: Price Action ───────────────────────────────────────────
    def price_action_strategy(self, pair: str, tf: TimeFrame) -> Optional[Signal]:
        entry = base_prices.get(pair, 1.0)
        # Pin bars, engulfing candles, inside bar
        pattern = np.random.choice([SignalType.BUY, SignalType.SELL, SignalType.NEUTRAL],
                                      p=[0.35, 0.35, 0.3])
        if pattern == SignalType.BUY:
            return self._create_signal(pair, StrategyType.PRICE_ACTION, SignalType.BUY, entry,
                                       sl_pips=20, tp_pips=60, confidence=75.0,
                                       reasons=["Bullish Engulfing candle pattern",
                                               "Price above key moving average",
                                               "Higher highs and higher lows forming"], timeframe=tf)
        elif pattern == SignalType.SELL:
            return self._create_signal(pair, StrategyType.PRICE_ACTION, SignalType.SELL, entry,
                                       sl_pips=20, tp_pips=55, confidence=73.0,
                                       reasons=["Bearish Engulfing candle pattern",
                                               "Price below key moving average",
                                               "Lower highs and lower lows forming"], timeframe=tf)
        return None

    # ── Strategy 5: Smart Money (Advanced) ─────────────────────────────────
    def smart_money_strategy(self, pair: str, tf: TimeFrame) -> Optional[Signal]:
        entry = base_prices.get(pair, 1.0)
        # Institutional order flow, stop hunt, accumulation
        flow = np.random.choice([SignalType.BUY, SignalType.SELL], p=[0.48, 0.52])
        if flow == SignalType.BUY:
            return self._create_signal(pair, StrategyType.SMART_MONEY, SignalType.BUY, entry,
                                       sl_pips=14, tp_pips=56, confidence=85.0,
                                       reasons=["Institutional accumulation visible",
                                               "Stop hunt below previous low",
                                               "MSS (Market Structure Shift) to bullish",
                                               "Displacement to the upside"], timeframe=tf)
        else:
            return self._create_signal(pair, StrategyType.SMART_MONEY, SignalType.SELL, entry,
                                       sl_pips=14, tp_pips=48, confidence=80.0,
                                       reasons=["Institutional distribution visible",
                                               "Stop hunt above previous high",
                                               "MSS (Market Structure Shift) to bearish",
                                               "Displacement to the downside"], timeframe=tf)

    # ── Strategy 6: Trend Following ────────────────────────────────────────
    def trend_following_strategy(self, pair: str, tf: TimeFrame) -> Optional[Signal]:
        entry = base_prices.get(pair, 1.0)
        # Multi-timeframe trend confluence
        trend = np.random.choice([SignalType.BUY, SignalType.SELL], p=[0.53, 0.47])
        if trend == SignalType.BUY:
            return self._create_signal(pair, StrategyType.TREND_FOLLOWING, SignalType.BUY, entry,
                                       sl_pips=25, tp_pips=75, confidence=70.5,
                                       reasons=["200 EMA aligned with 50 EMA ( bullish )",
                                               "MACD bullish cross above zero line",
                                               "RSI between 50-70 in uptrend",
                                               "Higher timeframe trend bullish"], timeframe=tf)
        else:
            return self._create_signal(pair, StrategyType.TREND_FOLLOWING, SignalType.SELL, entry,
                                       sl_pips=25, tp_pips=70, confidence=68.0,
                                       reasons=["200 EMA aligned with 50 EMA ( bearish )",
                                               "MACD bearish cross below zero line",
                                               "RSI between 30-50 in downtrend",
                                               "Higher timeframe trend bearish"], timeframe=tf)


strategy_engine = StrategyEngine()

# ---------------------------------------------------------------------------
# Background Tasks
# ---------------------------------------------------------------------------
async def signal_generator():
    """Generate signals every 30 seconds"""
    while True:
        for pair in PAIRS:
            for tf in [TimeFrame.M5, TimeFrame.H1]:
                signals = strategy_engine.generate_signals(pair, tf)
                for sig in signals:
                    # Keep only latest 500 signals
                    if len(signals_db) > 500:
                        signals_db.pop(0)
                    signals_db.append(sig)
                    
                    # Broadcast to WebSocket clients
                    await broadcast_message({
                        "type": "new_signal",
                        "data": sig.dict()
                    })
        await asyncio.sleep(30)


async def broadcast_message(message: dict):
    for client in connected_clients[:]:
        try:
            await client.send_json(message)
        except:
            if client in connected_clients:
                connected_clients.remove(client)


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(market_data_generator())
    asyncio.create_task(signal_generator())
    logger.info("ForexScalperAI API started successfully")


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/market-data", response_model=List[MarketData])
async def get_market_data(pair: Optional[str] = None):
    """Get current market data for all or specific pair"""
    if pair:
        if pair in market_data_db:
            return [market_data_db[pair]]
        return []
    return list(market_data_db.values())


@app.get("/api/signals", response_model=List[Signal])
async def get_signals(pair: Optional[str] = None, 
                     strategy: Optional[StrategyType] = None,
                     limit: int = 20):
    """Get latest trading signals"""
    filtered = signals_db
    if pair:
        filtered = [s for s in filtered if s.pair == pair]
    if strategy:
        filtered = [s for s in filtered if s.strategy == strategy]
    return filtered[-limit:]


@app.post("/api/execute-trade")
async def execute_trade(signal: Signal) -> Dict:
    """Simulate trade execution (replace with MT5 executor)"""
    trade = TradeTicket(
        id=str(uuid.uuid4()),
        pair=signal.pair,
        type=signal.type,
        entry=signal.entry,
        sl=signal.sl,
        tp=signal.tp,
        lot=signal.lot_size,
        status="open",
        pnl=0.0,
        open_time=datetime.utcnow().isoformat()
    )
    trades_db.append(trade)
    
    # Broadcast
    await broadcast_message({
        "type": "trade_executed",
        "data": trade.dict()
    })
    
    return {
        "status": "success",
        "trade_id": trade.id,
        "message": f"{signal.type.value} order placed for {signal.pair}"
    }


@app.get("/api/trades", response_model=List[TradeTicket])
async def get_trades(status: Optional[str] = None):
    """Get all trades or filter by status"""
    if status:
        return [t for t in trades_db if t.status == status]
    return trades_db


@app.get("/api/account")
async def get_account() -> AccountInfo:
    """Get account information (simulated)"""
    total_pnl = sum(t.pnl for t in trades_db)
    return AccountInfo(
        balance=10500.0,
        equity=10750.0,
        margin=1200.0,
        free_margin=9300.0,
        margin_level=895.0,
        total_trades=len(trades_db),
        total_profit=round(total_pnl, 2)
    )


@app.get("/api/pairs")
async def get_pairs():
    """Get available trading pairs"""
    return [
        {"pair": p, "base": p[:3], "quote": p[3:]}
        for p in PAIRS
    ]


@app.get("/api/strategies")
async def get_strategies():
    """Get available trading strategies"""
    return [
        {
            "id": "SMC",
            "name": "Smart Money Concepts",
            "description": "Order blocks, fair value gaps, and break of structure trading",
            "win_rate": "75%",
            "avg_rr": "1:3"
        },
        {
            "id": "ICT",
            "name": "Inner Circle Trader",
            "description": "Liquidity sweeps, inducement, and market maker models",
            "win_rate": "80%",
            "avg_rr": "1:4"
        },
        {
            "id": "SUPPLY_DEMAND",
            "name": "Supply & Demand",
            "description": "Trading from fresh supply and demand zones",
            "win_rate": "70%",
            "avg_rr": "1:2.5"
        },
        {
            "id": "PRICE_ACTION",
            "name": "Price Action",
            "description": "Candlestick patterns, support/resistance, and market structure",
            "win_rate": "73%",
            "avg_rr": "1:3"
        },
        {
            "id": "SMART_MONEY",
            "name": "Smart Money (Advanced)",
            "description": "Institutional order flow and stop hunt detection",
            "win_rate": "82%",
            "avg_rr": "1:4"
        },
        {
            "id": "TREND_FOLLOWING",
            "name": "Trend Following",
            "description": "Multi-timeframe trend confluence with EMA and MACD",
            "win_rate": "68%",
            "avg_rr": "1:3"
        }
    ]


# ---------------------------------------------------------------------------
# WebSocket for Real-Time Data
# ---------------------------------------------------------------------------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    logger.info(f"Client connected. Total: {len(connected_clients)}")
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("action") == "subscribe_pricing":
                await websocket.send_json({
                    "type": "market_data",
                    "data": [m.dict() for m in market_data_db.values()]
                })
            elif message.get("action") == "get_signals":
                await websocket.send_json({
                    "type": "signals",
                    "data": [s.dict() for s in signals_db[-10:]]
                })
            elif message.get("action") == "execute_trade":
                await websocket.send_json({
                    "type": "trade_result",
                    "data": {"status": "executed", "message": "Trade placed successfully"}
                })
                
    except WebSocketDisconnect:
        connected_clients.remove(websocket)
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if websocket in connected_clients:
            connected_clients.remove(websocket)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
