# backend/main.py
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import asyncio

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class MT5Trading:
    def __init__(self):
        self.connected = False
        
    def connect(self):
        if mt5.initialize():
            self.connected = True
            return True
        return False
    
    def get_price(self, symbol="EURUSD"):
        tick = mt5.symbol_info_tick(symbol)
        if tick:
            return {
                'bid': tick.bid,
                'ask': tick.ask,
                'spread': tick.ask - tick.bid,
                'volume': tick.volume,
                'timestamp': datetime.now().isoformat()
            }
        return None
    
    def generate_signal(self, symbol="EURUSD"):
        # SMC signal generation logic
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 100)
        if rates is None:
            return None
        
        df = pd.DataFrame(rates)
        current_price = self.get_price(symbol)['bid']
        
        # Calculate momentum
        close_prices = df['close'].values
        roc = ((close_prices[-1] - close_prices[-10]) / close_prices[-10]) * 100
        
        # Calculate ATR
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift())
        low_close = abs(df['low'] - df['close'].shift())
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(window=14).mean().iloc[-1]
        
        expected_move = atr * 0.3
        
        # Determine signal
        if roc > 0.1:
            signal_type = "BUY"
            confidence = 75
            tp1 = current_price + (expected_move * 0.6)
            tp2 = current_price + expected_move
            tp3 = current_price + (expected_move * 1.4)
            sl = current_price - (expected_move * 0.5)
        elif roc < -0.1:
            signal_type = "SELL"
            confidence = 75
            tp1 = current_price - (expected_move * 0.6)
            tp2 = current_price - expected_move
            tp3 = current_price - (expected_move * 1.4)
            sl = current_price + (expected_move * 0.5)
        else:
            signal_type = "NEUTRAL"
            confidence = 0
            tp1 = tp2 = tp3 = sl = current_price
        
        return {
            'type': signal_type,
            'confidence': confidence,
            'entry': current_price,
            'tp1': tp1,
            'tp2': tp2,
            'tp3': tp3,
            'sl': sl,
            'expected_move': expected_move,
            'generatedAt': datetime.now().isoformat(),
            'validUntil': (datetime.now() + timedelta(minutes=10)).isoformat(),
            'isActive': True,
            'tp1Hit': False,
            'tp2Hit': False,
            'tp3Hit': False,
            'slHit': False
        }

trading = MT5Trading()

@app.on_event("startup")
async def startup_event():
    trading.connect()

@app.get("/api/connect")
async def connect():
    if trading.connect():
        return {"status": "connected"}
    return {"status": "error"}

@app.get("/api/price/{symbol}")
async def get_price(symbol: str = "EURUSD"):
    return trading.get_price(symbol)

@app.get("/api/signal/{symbol}")
async def get_signal(symbol: str = "EURUSD"):
    return trading.generate_signal(symbol)