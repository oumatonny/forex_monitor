import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import MetaTrader5 as mt5
from datetime import datetime, timedelta
import time
import threading
import sys
import os
from collections import deque

# Page config
st.set_page_config(
    page_title="SMC Trading Dashboard - 10 Min Signals",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for clean white background
st.markdown("""
<style>
    /* Main background */
    .stApp {
        background-color: #ffffff;
    }
    .main {
        background-color: #ffffff;
    }
    
    /* Price cards */
    .price-card {
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        border-radius: 10px;
        padding: 15px;
        margin: 5px;
        border: 1px solid #dee2e6;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .bid-card {
        border-left: 4px solid #dc3545;
    }
    .ask-card {
        border-left: 4px solid #28a745;
    }
    .price-label {
        color: #6c757d;
        font-size: 12px;
        letter-spacing: 1px;
        font-weight: 600;
    }
    .price-value {
        color: #000000;
        font-size: 28px;
        font-weight: bold;
        font-family: 'Courier New', monospace;
    }
    .spread-value {
        color: #ffc107;
        font-size: 18px;
        font-weight: bold;
    }
    .change-positive {
        color: #28a745;
        font-weight: bold;
    }
    .change-negative {
        color: #dc3545;
        font-weight: bold;
    }
    .status-connected {
        color: #28a745;
        font-weight: bold;
    }
    .status-disconnected {
        color: #dc3545;
        font-weight: bold;
    }
    
    /* Signal boxes */
    .signal-buy {
        background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%);
        border-left: 4px solid #28a745;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
        color: #155724;
    }
    .signal-sell {
        background: linear-gradient(135deg, #f8d7da 0%, #f5c6cb 100%);
        border-left: 4px solid #dc3545;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
        color: #721c24;
    }
    .signal-neutral {
        background: linear-gradient(135deg, #fff3cd 0%, #ffeaa7 100%);
        border-left: 4px solid #ffc107;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
        color: #856404;
    }
    
    /* Level colors */
    .level-buy {
        color: #28a745;
        font-weight: bold;
    }
    .level-sell {
        color: #dc3545;
        font-weight: bold;
    }
    
    /* Timer styling */
    .timer-box {
        background: #f8f9fa;
        border-radius: 10px;
        padding: 10px;
        text-align: center;
        border: 2px solid #007bff;
        margin: 10px 0;
    }
    .timer-value {
        font-size: 24px;
        font-weight: bold;
        color: #007bff;
    }
    
    /* Sidebar styling */
    .css-1d391kg {
        background-color: #f8f9fa;
    }
    
    /* Headers */
    h1, h2, h3, h4 {
        color: #000000 !important;
    }
    
    /* Metrics */
    .stMetric {
        background-color: #f8f9fa;
        padding: 10px;
        border-radius: 8px;
    }
    
    /* Expander */
    .streamlit-expanderHeader {
        background-color: #f8f9fa;
        color: #000000;
    }
    
    /* Buttons */
    .stButton > button {
        background-color: #007bff;
        color: white;
        border: none;
        border-radius: 5px;
        padding: 8px 16px;
        font-weight: bold;
    }
    .stButton > button:hover {
        background-color: #0056b3;
        color: white;
    }
    
    /* Select boxes */
    .stSelectbox label {
        color: #000000 !important;
        font-weight: 600;
    }
    
    /* Scrollbar */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    ::-webkit-scrollbar-track {
        background: #f1f1f1;
    }
    ::-webkit-scrollbar-thumb {
        background: #888;
        border-radius: 4px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: #555;
    }
    
    /* Info boxes */
    .stInfo {
        background-color: #e7f3ff;
        color: #004085;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'mt5_initialized' not in st.session_state:
    st.session_state.mt5_initialized = False
if 'current_prices' not in st.session_state:
    st.session_state.current_prices = {}
if 'price_history' not in st.session_state:
    st.session_state.price_history = {}
if 'last_update' not in st.session_state:
    st.session_state.last_update = None
if 'mt5_data' not in st.session_state:
    st.session_state.mt5_data = None
if 'selected_pair' not in st.session_state:
    st.session_state.selected_pair = "EURUSD"
if 'timeframe' not in st.session_state:
    st.session_state.timeframe = "M5"  # Changed to M5 for better 10-min predictions
if 'chart_type' not in st.session_state:
    st.session_state.chart_type = "Candlestick"
if 'show_volume' not in st.session_state:
    st.session_state.show_volume = True
if 'auto_refresh' not in st.session_state:
    st.session_state.auto_refresh = True
if 'refresh_rate' not in st.session_state:
    st.session_state.refresh_rate = 5  # Refresh every 5 seconds

# Signal timing variables
if 'signal_generated_time' not in st.session_state:
    st.session_state.signal_generated_time = None
if 'current_signal' not in st.session_state:
    st.session_state.current_signal = None
if 'signal_valid_until' not in st.session_state:
    st.session_state.signal_valid_until = None
if 'next_signal_time' not in st.session_state:
    st.session_state.next_signal_time = None
if 'prediction_start_time' not in st.session_state:
    st.session_state.prediction_start_time = None
if 'price_at_signal' not in st.session_state:
    st.session_state.price_at_signal = None

class SMCPredictor:
    """SMC Predictor with 10-minute prediction window"""
    
    def __init__(self, df, digits, pair):
        self.df = df
        self.digits = digits
        self.pair = pair
        
    def calculate_support_resistance(self):
        """Calculate dynamic support and resistance levels"""
        recent_highs = self.df['high'].tail(20).max()
        recent_lows = self.df['low'].tail(20).min()
        current_price = self.df['close'].iloc[-1]
        
        # Calculate pivot points
        pivot = (recent_highs + recent_lows + self.df['close'].iloc[-1]) / 3
        r1 = 2 * pivot - recent_lows
        r2 = pivot + (recent_highs - recent_lows)
        s1 = 2 * pivot - recent_highs
        s2 = pivot - (recent_highs - recent_lows)
        
        return {
            'resistance': [r1, r2],
            'support': [s1, s2],
            'pivot': pivot
        }
    
    def calculate_momentum(self):
        """Calculate momentum indicators for 10-min prediction"""
        close_prices = self.df['close'].values
        
        # Rate of Change (ROC) for 10 periods
        if len(close_prices) > 10:
            roc = ((close_prices[-1] - close_prices[-10]) / close_prices[-10]) * 100
        else:
            roc = 0
        
        # Price velocity (momentum)
        if len(close_prices) > 5:
            velocity = (close_prices[-1] - close_prices[-5]) / close_prices[-5] * 100
        else:
            velocity = 0
        
        # Volume momentum
        if 'tick_volume' in self.df.columns:
            vol_momentum = self.df['tick_volume'].tail(5).mean() / self.df['tick_volume'].tail(20).mean()
        else:
            vol_momentum = 1
        
        return {
            'roc': roc,
            'velocity': velocity,
            'volume_momentum': vol_momentum
        }
    
    def identify_order_flow(self):
        """Identify institutional order flow"""
        order_flow = {'bullish': 0, 'bearish': 0}
        
        # Analyze last 10 candles for order flow
        for i in range(-10, 0):
            candle = self.df.iloc[i]
            body = abs(candle['close'] - candle['open'])
            wick_upper = candle['high'] - max(candle['close'], candle['open'])
            wick_lower = min(candle['close'], candle['open']) - candle['low']
            
            # Long wicks indicate rejection
            if wick_upper > body * 1.5:
                order_flow['bearish'] += 1
            if wick_lower > body * 1.5:
                order_flow['bullish'] += 1
        
        return order_flow
    
    def generate_10min_prediction(self, current_price):
        """Generate prediction valid for next 10 minutes"""
        
        sr_levels = self.calculate_support_resistance()
        momentum = self.calculate_momentum()
        order_flow = self.identify_order_flow()
        
        # Calculate expected move in 10 minutes (based on ATR)
        atr = self.calculate_atr()
        expected_move_10min = atr * 0.3  # 30% of hourly ATR for 10min
        
        # Determine direction
        bullish_score = 0
        bearish_score = 0
        
        # Momentum signals
        if momentum['roc'] > 0.1:
            bullish_score += 2
        elif momentum['roc'] < -0.1:
            bearish_score += 2
        
        if momentum['velocity'] > 0.05:
            bullish_score += 1
        elif momentum['velocity'] < -0.05:
            bearish_score += 1
        
        # Volume confirmation
        if momentum['volume_momentum'] > 1.2:
            if bullish_score > bearish_score:
                bullish_score += 2
            else:
                bearish_score += 2
        
        # Order flow
        if order_flow['bullish'] > order_flow['bearish']:
            bullish_score += 2
        elif order_flow['bearish'] > order_flow['bullish']:
            bearish_score += 2
        
        # Price position relative to pivot
        if current_price < sr_levels['pivot']:
            bullish_score += 1
        else:
            bearish_score += 1
        
        # Generate signal
        if bullish_score > bearish_score and bullish_score >= 3:
            signal_type = 'BUY'
            confidence = min(90, 50 + (bullish_score * 8))
            
            # Calculate TP levels for 10 minutes
            tp1 = current_price + (expected_move_10min * 0.6)
            tp2 = current_price + (expected_move_10min * 1.0)
            tp3 = current_price + (expected_move_10min * 1.4)
            sl = current_price - (expected_move_10min * 0.5)
            
            # Adjust TP based on resistance levels
            for resistance in sr_levels['resistance']:
                if resistance > current_price and resistance < tp2:
                    tp2 = resistance
                    tp3 = resistance + (expected_move_10min * 0.4)
            
        elif bearish_score > bullish_score and bearish_score >= 3:
            signal_type = 'SELL'
            confidence = min(90, 50 + (bearish_score * 8))
            
            # Calculate TP levels for 10 minutes
            tp1 = current_price - (expected_move_10min * 0.6)
            tp2 = current_price - (expected_move_10min * 1.0)
            tp3 = current_price - (expected_move_10min * 1.4)
            sl = current_price + (expected_move_10min * 0.5)
            
            # Adjust TP based on support levels
            for support in sr_levels['support']:
                if support < current_price and support > tp2:
                    tp2 = support
                    tp3 = support - (expected_move_10min * 0.4)
        else:
            signal_type = 'NEUTRAL'
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
            'expected_move': expected_move_10min,
            'bullish_score': bullish_score,
            'bearish_score': bearish_score,
            'momentum': momentum,
            'sr_levels': sr_levels
        }
    
    def calculate_atr(self, period=14):
        """Calculate Average True Range"""
        high_low = self.df['high'] - self.df['low']
        high_close = abs(self.df['high'] - self.df['close'].shift())
        low_close = abs(self.df['low'] - self.df['close'].shift())
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(window=period).mean().iloc[-1]
        return atr

class RealMT5Data:
    """Real MT5 data connection handler"""
    
    def __init__(self):
        self.connected = False
        self.symbols = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "BTCUSD", "NZDUSD", "USDCHF"]
        
    def connect(self):
        """Connect to MT5 terminal"""
        try:
            mt5_path = None
            if sys.platform == "win32":
                possible_paths = [
                    "C:\\Program Files\\MetaTrader 5\\terminal64.exe",
                    "C:\\Program Files (x86)\\MetaTrader 5\\terminal.exe",
                    os.path.expanduser("~\\AppData\\Local\\Programs\\MetaTrader 5\\terminal64.exe")
                ]
                for path in possible_paths:
                    if os.path.exists(path):
                        mt5_path = path
                        break
            
            if mt5_path:
                initialized = mt5.initialize(mt5_path)
            else:
                initialized = mt5.initialize()
            
            if not initialized:
                st.error(f"MT5 initialization failed. Error: {mt5.last_error()}")
                return False
            
            self.connected = True
            
            for symbol in self.symbols:
                if not mt5.symbol_select(symbol, True):
                    st.warning(f"Symbol {symbol} not available")
            
            return True
            
        except Exception as e:
            st.error(f"MT5 connection error: {str(e)}")
            return False
    
    def disconnect(self):
        """Disconnect from MT5"""
        if self.connected:
            mt5.shutdown()
            self.connected = False
    
    def get_tick(self, symbol):
        """Get current tick data"""
        if not self.connected:
            return None
        
        try:
            tick = mt5.symbol_info_tick(symbol)
            if tick:
                return {
                    'bid': tick.bid,
                    'ask': tick.ask,
                    'spread': tick.ask - tick.bid,
                    'volume': tick.volume,
                    'time': datetime.fromtimestamp(tick.time)
                }
        except Exception as e:
            st.error(f"Error getting tick: {e}")
        return None
    
    def get_rates(self, symbol, timeframe=mt5.TIMEFRAME_M5, count=100):
        """Get historical rates"""
        if not self.connected:
            return None
        
        try:
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
            if rates is not None and len(rates) > 0:
                df = pd.DataFrame(rates)
                df['time'] = pd.to_datetime(df['time'], unit='s')
                return df
        except Exception as e:
            st.error(f"Error getting rates: {e}")
        return None
    
    def get_symbol_info(self, symbol):
        """Get symbol information"""
        if not self.connected:
            return None
        
        try:
            info = mt5.symbol_info(symbol)
            if info:
                return {
                    'name': info.name,
                    'digits': info.digits,
                    'point': info.point,
                    'description': info.description
                }
        except Exception as e:
            st.error(f"Error getting info: {e}")
        return None

# Initialize MT5
def init_mt5():
    if st.session_state.mt5_data is None:
        mt5_data = RealMT5Data()
        if mt5_data.connect():
            st.session_state.mt5_data = mt5_data
            return mt5_data
    return st.session_state.mt5_data

def get_timeframe(timeframe_str):
    timeframe_map = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1,
    }
    return timeframe_map.get(timeframe_str, mt5.TIMEFRAME_M5)

def generate_new_signal(mt5_data, selected_pair, timeframe, digits):
    """Generate new signal every 20 minutes"""
    mt5_timeframe = get_timeframe(timeframe)
    historical_data = mt5_data.get_rates(selected_pair, mt5_timeframe, 100)
    
    if historical_data is not None and len(historical_data) > 0:
        tick_data = mt5_data.get_tick(selected_pair)
        if tick_data:
            current_price = (tick_data['bid'] + tick_data['ask']) / 2
            
            predictor = SMCPredictor(historical_data, digits, selected_pair)
            signal = predictor.generate_10min_prediction(current_price)
            
            # Store signal info
            st.session_state.current_signal = signal
            st.session_state.signal_generated_time = datetime.now()
            st.session_state.signal_valid_until = datetime.now() + timedelta(minutes=10)
            st.session_state.next_signal_time = datetime.now() + timedelta(minutes=20)
            st.session_state.price_at_signal = current_price
            
            return signal
    return None

# Main app
st.title("📈 SMC Trading Dashboard - 10 Minute Predictions")
st.markdown("**Smart Money Concepts with 10-minute price predictions | Signals refresh every 20 minutes**")

# Sidebar
with st.sidebar:
    st.markdown("## 🔌 MT5 Connection")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔌 Connect MT5", use_container_width=True):
            with st.spinner("Connecting to MT5..."):
                mt5_data = init_mt5()
                if mt5_data and mt5_data.connected:
                    st.session_state.mt5_initialized = True
                    # Generate first signal immediately
                    if st.session_state.selected_pair:
                        symbol_info = mt5_data.get_symbol_info(st.session_state.selected_pair)
                        digits = symbol_info['digits'] if symbol_info else 5
                        generate_new_signal(mt5_data, st.session_state.selected_pair, 
                                          st.session_state.timeframe, digits)
                    st.success("Connected!")
                    time.sleep(1)
                    st.rerun()
    
    with col2:
        if st.button("❌ Disconnect", use_container_width=True):
            if st.session_state.mt5_data:
                st.session_state.mt5_data.disconnect()
                st.session_state.mt5_data = None
            st.session_state.mt5_initialized = False
            st.session_state.current_signal = None
            st.success("Disconnected")
            time.sleep(1)
            st.rerun()
    
    # Connection status
    mt5_data = st.session_state.mt5_data if st.session_state.mt5_initialized else None
    
    if mt5_data and mt5_data.connected:
        st.markdown("### Status: <span class='status-connected'>● CONNECTED</span>", unsafe_allow_html=True)
        
        account_info = mt5.account_info()
        if account_info:
            st.markdown("---")
            st.markdown("### 💼 Account Info")
            st.metric("Balance", f"${account_info.balance:,.2f}")
            st.metric("Equity", f"${account_info.equity:,.2f}")
    else:
        st.markdown("### Status: <span class='status-disconnected'>● DISCONNECTED</span>", unsafe_allow_html=True)
        st.info("⚠️ Click 'Connect MT5' to start")
    
    st.markdown("---")
    
    # Symbol selection
    if mt5_data and mt5_data.connected:
        available_symbols = []
        for s in mt5_data.symbols:
            if mt5.symbol_info(s):
                available_symbols.append(s)
        
        if available_symbols:
            new_pair = st.selectbox(
                "🔍 Select Symbol",
                options=available_symbols,
                index=available_symbols.index(st.session_state.selected_pair) if st.session_state.selected_pair in available_symbols else 0,
                format_func=lambda x: f"{x}"
            )
            
            if new_pair != st.session_state.selected_pair:
                st.session_state.selected_pair = new_pair
                # Generate new signal for new pair
                symbol_info = mt5_data.get_symbol_info(new_pair)
                digits = symbol_info['digits'] if symbol_info else 5
                generate_new_signal(mt5_data, new_pair, st.session_state.timeframe, digits)
                st.rerun()
        
        st.session_state.timeframe = st.selectbox(
            "⏱️ Timeframe",
            options=["M1", "M5", "M15", "M30", "H1"],
            index=1  # M5 default
        )
        
        st.markdown("---")
        st.markdown("### ⏰ Signal Timing")
        st.markdown(f"**Signal Validity:** 10 minutes")
        st.markdown(f"**New Signal Every:** 20 minutes")
        
        # Timer display
        if st.session_state.signal_valid_until:
            remaining = (st.session_state.signal_valid_until - datetime.now()).total_seconds()
            if remaining > 0:
                minutes = int(remaining // 60)
                seconds = int(remaining % 60)
                st.markdown(f"""
                <div class='timer-box'>
                    <div class='price-label'>SIGNAL VALID FOR</div>
                    <div class='timer-value'>{minutes:02d}:{seconds:02d}</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.warning("⚠️ Signal expired - waiting for next signal")
        
        if st.session_state.next_signal_time:
            next_signal = (st.session_state.next_signal_time - datetime.now()).total_seconds()
            if next_signal > 0:
                minutes = int(next_signal // 60)
                seconds = int(next_signal % 60)
                st.markdown(f"""
                <div class='timer-box'>
                    <div class='price-label'>NEXT SIGNAL IN</div>
                    <div class='timer-value'>{minutes:02d}:{seconds:02d}</div>
                </div>
                """, unsafe_allow_html=True)

# Main content area
mt5_data = st.session_state.mt5_data if st.session_state.mt5_initialized else None

if mt5_data and mt5_data.connected and st.session_state.selected_pair:
    
    symbol_info = mt5_data.get_symbol_info(st.session_state.selected_pair)
    digits = symbol_info['digits'] if symbol_info else 5
    
    tick_data = mt5_data.get_tick(st.session_state.selected_pair)
    
    if tick_data:
        # Display current prices
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.markdown(f"""
            <div class='price-card bid-card'>
                <div class='price-label'>BID</div>
                <div class='price-value'>{tick_data['bid']:.{digits}f}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class='price-card ask-card'>
                <div class='price-label'>ASK</div>
                <div class='price-value'>{tick_data['ask']:.{digits}f}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            if st.session_state.selected_pair == "USDJPY":
                spread_pips = tick_data['spread'] * 100
            else:
                spread_pips = tick_data['spread'] * 10000
            st.markdown(f"""
            <div class='price-card'>
                <div class='price-label'>SPREAD</div>
                <div class='spread-value'>{spread_pips:.1f} pips</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            st.markdown(f"""
            <div class='price-card'>
                <div class='price-label'>VOLUME</div>
                <div class='price-value'>{tick_data['volume']:,}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col5:
            st.markdown(f"""
            <div class='price-card'>
                <div class='price-label'>LAST UPDATE</div>
                <div class='price-value' style='font-size: 14px;'>{tick_data['time'].strftime('%H:%M:%S')}</div>
            </div>
            """, unsafe_allow_html=True)
        
        # Check if we need to generate new signal (every 20 minutes)
        if st.session_state.next_signal_time and datetime.now() >= st.session_state.next_signal_time:
            generate_new_signal(mt5_data, st.session_state.selected_pair, 
                              st.session_state.timeframe, digits)
            st.rerun()
        
        # Generate initial signal if none exists
        if st.session_state.current_signal is None:
            generate_new_signal(mt5_data, st.session_state.selected_pair, 
                              st.session_state.timeframe, digits)
        
        # Display current signal
        if st.session_state.current_signal:
            signal = st.session_state.current_signal
            current_price = (tick_data['bid'] + tick_data['ask']) / 2
            
            st.markdown("---")
            st.markdown("## 🎯 Active Trading Signal (Valid for 10 minutes)")
            
            # Display signal based on type
            if signal['type'] == 'BUY':
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.markdown(f"""
                    <div class='signal-buy'>
                        <h2>🟢 BUY SIGNAL ACTIVE</h2>
                        <p><strong>Confidence:</strong> {signal['confidence']:.0f}%</p>
                        <p><strong>Expected Move (10min):</strong> {signal['expected_move']:.{digits}f} pips</p>
                        <hr>
                        <h4>📈 Entry Zone</h4>
                        <p><span class='level-buy'>BUY at: {signal['entry']:.{digits}f}</span></p>
                        <p><strong>Current Price:</strong> {current_price:.{digits}f}</p>
                        <hr>
                        <h4>🎯 Take Profit Levels</h4>
                        <p><strong>TP1 (Conservative):</strong> {signal['tp1']:.{digits}f} <span style='color:#666'> (Risk/Reward: 1:0.6)</span></p>
                        <p><strong>TP2 (Target):</strong> {signal['tp2']:.{digits}f} <span style='color:#666'> (Risk/Reward: 1:1)</span></p>
                        <p><strong>TP3 (Aggressive):</strong> {signal['tp3']:.{digits}f} <span style='color:#666'> (Risk/Reward: 1:1.4)</span></p>
                        <hr>
                        <h4>🛑 Stop Loss</h4>
                        <p><strong>SL:</strong> {signal['sl']:.{digits}f} <span style='color:#666'> (-0.5x expected move)</span></p>
                        <hr>
                        <p><strong>📊 Momentum Score:</strong> +{signal['bullish_score']}</p>
                        <p><strong>📈 ROC (10-period):</strong> {signal['momentum']['roc']:+.2f}%</p>
                        <p><strong>⚡ Price Velocity:</strong> {signal['momentum']['velocity']:+.2f}%</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    # Risk/Reward visualization
                    risk = abs(signal['entry'] - signal['sl'])
                    reward = abs(signal['tp2'] - signal['entry'])
                    rr = reward / risk if risk > 0 else 0
                    st.markdown(f"""
                    <div class='price-card'>
                        <h4>Risk/Reward</h4>
                        <div class='price-value'>1:{rr:.2f}</div>
                        <hr>
                        <h4>Signal Strength</h4>
                        <div class='price-value' style='color:#28a745'>{'⭐' * min(5, int(signal['confidence']/20))}</div>
                        <hr>
                        <h4>Recommended</h4>
                        <p><strong>Position Size:</strong> 0.5-1% risk</p>
                        <p><strong>Time Horizon:</strong> 10 minutes</p>
                    </div>
                    """, unsafe_allow_html=True)
            
            elif signal['type'] == 'SELL':
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.markdown(f"""
                    <div class='signal-sell'>
                        <h2>🔴 SELL SIGNAL ACTIVE</h2>
                        <p><strong>Confidence:</strong> {signal['confidence']:.0f}%</p>
                        <p><strong>Expected Move (10min):</strong> {signal['expected_move']:.{digits}f} pips</p>
                        <hr>
                        <h4>📉 Entry Zone</h4>
                        <p><span class='level-sell'>SELL at: {signal['entry']:.{digits}f}</span></p>
                        <p><strong>Current Price:</strong> {current_price:.{digits}f}</p>
                        <hr>
                        <h4>🎯 Take Profit Levels</h4>
                        <p><strong>TP1 (Conservative):</strong> {signal['tp1']:.{digits}f} <span style='color:#666'> (Risk/Reward: 1:0.6)</span></p>
                        <p><strong>TP2 (Target):</strong> {signal['tp2']:.{digits}f} <span style='color:#666'> (Risk/Reward: 1:1)</span></p>
                        <p><strong>TP3 (Aggressive):</strong> {signal['tp3']:.{digits}f} <span style='color:#666'> (Risk/Reward: 1:1.4)</span></p>
                        <hr>
                        <h4>🛑 Stop Loss</h4>
                        <p><strong>SL:</strong> {signal['sl']:.{digits}f} <span style='color:#666'> (+0.5x expected move)</span></p>
                        <hr>
                        <p><strong>📊 Momentum Score:</strong> -{signal['bearish_score']}</p>
                        <p><strong>📉 ROC (10-period):</strong> {signal['momentum']['roc']:+.2f}%</p>
                        <p><strong>⚡ Price Velocity:</strong> {signal['momentum']['velocity']:+.2f}%</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    risk = abs(signal['sl'] - signal['entry'])
                    reward = abs(signal['entry'] - signal['tp2'])
                    rr = reward / risk if risk > 0 else 0
                    st.markdown(f"""
                    <div class='price-card'>
                        <h4>Risk/Reward</h4>
                        <div class='price-value'>1:{rr:.2f}</div>
                        <hr>
                        <h4>Signal Strength</h4>
                        <div class='price-value' style='color:#dc3545'>{'⭐' * min(5, int(signal['confidence']/20))}</div>
                        <hr>
                        <h4>Recommended</h4>
                        <p><strong>Position Size:</strong> 0.5-1% risk</p>
                        <p><strong>Time Horizon:</strong> 10 minutes</p>
                    </div>
                    """, unsafe_allow_html=True)
            
            else:
                st.markdown(f"""
                <div class='signal-neutral'>
                    <h2>🟡 NEUTRAL SIGNAL</h2>
                    <p>No clear directional bias for the next 10 minutes</p>
                    <p><strong>Bullish Score:</strong> {signal['bullish_score']} | <strong>Bearish Score:</strong> {signal['bearish_score']}</p>
                    <hr>
                    <p><strong>💡 Recommendation:</strong> Wait for next signal in {max(0, int((st.session_state.next_signal_time - datetime.now()).total_seconds() // 60))} minutes</p>
                    <p><strong>📊 Current ROC:</strong> {signal['momentum']['roc']:+.2f}%</p>
                    <p><strong>⚡ Price Velocity:</strong> {signal['momentum']['velocity']:+.2f}%</p>
                </div>
                """, unsafe_allow_html=True)
        
        # Get historical data for chart
        mt5_timeframe = get_timeframe(st.session_state.timeframe)
        historical_data = mt5_data.get_rates(st.session_state.selected_pair, mt5_timeframe, 100)
        
        if historical_data is not None:
            st.markdown("---")
            st.markdown("### 📊 Price Chart")
            
            # Create chart
            fig = go.Figure()
            
            fig.add_trace(
                go.Candlestick(
                    x=historical_data['time'],
                    open=historical_data['open'],
                    high=historical_data['high'],
                    low=historical_data['low'],
                    close=historical_data['close'],
                    name=st.session_state.selected_pair,
                    increasing_line_color='#28a745',
                    decreasing_line_color='#dc3545'
                )
            )
            
            # Add signal levels if available
            if st.session_state.current_signal and st.session_state.current_signal['type'] != 'NEUTRAL':
                signal = st.session_state.current_signal
                fig.add_hline(y=signal['entry'], line_color="#ffc107", line_width=2,
                            annotation_text="ENTRY", annotation_position="top left")
                fig.add_hline(y=signal['sl'], line_dash="dot", line_color="#dc3545",
                            annotation_text="SL", annotation_position="bottom left")
                fig.add_hline(y=signal['tp1'], line_dash="dot", line_color="#28a745",
                            annotation_text="TP1", annotation_position="top right")
                fig.add_hline(y=signal['tp2'], line_dash="dot", line_color="#28a745",
                            annotation_text="TP2", annotation_position="top right")
                fig.add_hline(y=signal['tp3'], line_dash="dot", line_color="#28a745",
                            annotation_text="TP3", annotation_position="top right")
            
            fig.update_layout(
                template='plotly_white',
                title=f"{st.session_state.selected_pair} - {st.session_state.timeframe} Chart",
                height=500,
                margin=dict(l=50, r=50, t=50, b=50),
                xaxis_rangeslider_visible=False
            )
            
            fig.update_xaxes(gridcolor='#e9ecef', showgrid=True)
            fig.update_yaxes(gridcolor='#e9ecef', showgrid=True)
            
            st.plotly_chart(fig, use_container_width=True)
    
    # Auto-refresh
    if st.session_state.auto_refresh:
        time.sleep(st.session_state.refresh_rate)
        st.rerun()

else:
    st.info("🔌 Please connect to MT5 to start receiving 10-minute trading signals")
    
    with st.expander("📖 How it Works", expanded=True):
        st.markdown("""
        ### ⏰ **10-Minute Prediction System**
        
        **How signals work:**
        - 🔄 **New signal generated every 20 minutes**
        - ⏱️ **Each signal is valid for 10 minutes**
        - 📊 **Predicts price direction for next 10 minutes**
        - 🎯 **Provides 3 Take Profit levels with different risk/reward ratios**
        - 🛑 **Includes Stop Loss based on expected volatility**
        
        **Signal Components:**
        1. **Momentum Analysis** - Rate of Change & Price Velocity
        2. **Order Flow** - Institutional buying/selling pressure
        3. **Support/Resistance** - Key price levels
        4. **Volume Confirmation** - Tick volume momentum
        
        **Trading Guidelines:**
        - Enter within 2-3 minutes of signal generation
        - Use TP1 for conservative targets (60% of expected move)
        - Use TP2 for standard targets (100% of expected move)
        - Use TP3 for aggressive targets (140% of expected move)
        - Always use Stop Loss for risk management
        """)

# Footer
st.markdown("---")
st.caption(f"🎯 10-Minute SMC Predictions | Signals valid for 10 minutes, refresh every 20 minutes | Last update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")