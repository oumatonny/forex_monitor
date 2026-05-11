import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import MetaTrader5 as mt5
from datetime import datetime, timedelta
import time
import sys
import os
import csv

LOG_FILE = os.path.join(os.path.dirname(__file__), "trade_log.csv")
LOG_COLUMNS = ["Date", "Time", "Pair", "Type", "Lot", "Entry",
               "SL", "TP", "Confidence", "Ticket", "Close_Price",
               "PnL", "Status", "Source"]

def _load_log():
    if not os.path.exists(LOG_FILE):
        return []
    try:
        with open(LOG_FILE, newline='', encoding='utf-8') as f:
            return list(csv.DictReader(f))
    except Exception:
        return []

def _save_log(records):
    try:
        with open(LOG_FILE, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=LOG_COLUMNS, extrasaction='ignore')
            w.writeheader()
            w.writerows(records)
    except Exception:
        pass

def _append_log(record: dict):
    records = _load_log()
    records.append(record)
    _save_log(records)

st.set_page_config(
    page_title="SMC Auto Trader",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .stApp, .main { background-color: #ffffff; }
    .price-card {
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        border-radius: 10px; padding: 15px; margin: 5px;
        border: 1px solid #dee2e6; text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .bid-card  { border-left: 4px solid #dc3545; }
    .ask-card  { border-left: 4px solid #28a745; }
    .price-label { color: #6c757d; font-size: 12px; letter-spacing: 1px; font-weight: 600; }
    .price-value { color: #000; font-size: 26px; font-weight: bold; font-family: 'Courier New', monospace; }
    .spread-value { color: #ffc107; font-size: 18px; font-weight: bold; }
    .status-connected   { color: #28a745; font-weight: bold; }
    .status-disconnected{ color: #dc3545; font-weight: bold; }
    .signal-buy {
        background: linear-gradient(135deg,#d4edda,#c3e6cb);
        border-left: 4px solid #28a745; padding: 15px; border-radius: 8px;
        margin: 10px 0; color: #155724;
    }
    .signal-sell {
        background: linear-gradient(135deg,#f8d7da,#f5c6cb);
        border-left: 4px solid #dc3545; padding: 15px; border-radius: 8px;
        margin: 10px 0; color: #721c24;
    }
    .signal-neutral {
        background: linear-gradient(135deg,#fff3cd,#ffeaa7);
        border-left: 4px solid #ffc107; padding: 15px; border-radius: 8px;
        margin: 10px 0; color: #856404;
    }
    .timer-box {
        background: #f8f9fa; border-radius: 10px; padding: 10px;
        text-align: center; border: 2px solid #007bff; margin: 8px 0;
    }
    .timer-value { font-size: 22px; font-weight: bold; color: #007bff; }
    .at-on  { background:#d4edda; border:2px solid #28a745; border-radius:8px;
               padding:8px; text-align:center; color:#155724; font-weight:bold; }
    .at-off { background:#f8d7da; border:2px solid #dc3545; border-radius:8px;
               padding:8px; text-align:center; color:#721c24; font-weight:bold; }
    h1,h2,h3,h4 { color:#000 !important; }
    .stButton>button {
        background-color:#007bff; color:white; border:none;
        border-radius:5px; padding:8px 16px; font-weight:bold;
    }
    .stButton>button:hover { background-color:#0056b3; }
</style>
""", unsafe_allow_html=True)

# ── Session state defaults ────────────────────────────────────────────────────
_defaults = {
    'mt5_initialized': False,
    'mt5_data': None,
    'selected_pair': "EURUSD",
    'timeframe': "M5",
    'auto_refresh': True,
    'refresh_rate': 5,
    'current_signal': None,
    'signal_generated_time': None,
    'signal_valid_until': None,
    'next_signal_time': None,
    'price_at_signal': None,
    'auto_trade_enabled': False,
    'auto_trade_risk_pct': 1.0,
    'auto_trade_tp': 'TP2',
    'auto_trade_min_conf': 65,
    'last_auto_trade_signal': None,
    'trade_history': _load_log(),
}
for _k, _v in _defaults.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ══════════════════════════════════════════════════════════════════════════════
# SMC PREDICTOR — multi-factor confluence
# ══════════════════════════════════════════════════════════════════════════════
class SMCPredictor:
    def __init__(self, df: pd.DataFrame, digits: int, pair: str):
        self.df     = df.copy().reset_index(drop=True)
        self.digits = digits
        self.pair   = pair

    # ── Technical indicators ─────────────────────────────────────────────────

    def _ema(self, period: int) -> pd.Series:
        return self.df['close'].ewm(span=period, adjust=False).mean()

    def _rsi(self, period: int = 14) -> pd.Series:
        delta = self.df['close'].diff()
        gain  = delta.clip(lower=0).rolling(period).mean()
        loss  = (-delta.clip(upper=0)).rolling(period).mean()
        rs    = gain / loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))

    def _macd(self):
        fast   = self.df['close'].ewm(span=12, adjust=False).mean()
        slow   = self.df['close'].ewm(span=26, adjust=False).mean()
        line   = fast - slow
        signal = line.ewm(span=9, adjust=False).mean()
        return line, signal

    def _atr(self, period: int = 14) -> float:
        hl = self.df['high'] - self.df['low']
        hc = (self.df['high'] - self.df['close'].shift()).abs()
        lc = (self.df['low']  - self.df['close'].shift()).abs()
        tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
        return float(tr.rolling(period).mean().iloc[-1])

    # ── Market structure ─────────────────────────────────────────────────────

    def _swing_highs_lows(self, lookback: int = 5):
        highs, lows = [], []
        n = len(self.df)
        for i in range(lookback, n - lookback):
            window_h = self.df['high'].iloc[i - lookback: i + lookback + 1]
            window_l = self.df['low'].iloc[i  - lookback: i + lookback + 1]
            if self.df['high'].iloc[i] == window_h.max():
                highs.append((i, float(self.df['high'].iloc[i])))
            if self.df['low'].iloc[i] == window_l.min():
                lows.append((i, float(self.df['low'].iloc[i])))
        return highs, lows

    def _bos_choch(self) -> dict:
        highs, lows = self._swing_highs_lows()
        last_close  = float(self.df['close'].iloc[-1])
        result = {'bos_bullish': False, 'bos_bearish': False, 'choch': False}
        if len(highs) >= 2 and last_close > highs[-2][1]:
            result['bos_bullish'] = True
        if len(lows) >= 2 and last_close < lows[-2][1]:
            result['bos_bearish'] = True
        if result['bos_bullish'] and len(lows) >= 2 and lows[-1][1] > lows[-2][1]:
            result['choch'] = True
        return result

    def _fair_value_gaps(self):
        """Returns (bull_fvgs, bear_fvgs) each a list of (low, high) tuples."""
        bull_fvgs, bear_fvgs = [], []
        df = self.df
        for i in range(2, len(df)):
            if df['low'].iloc[i] > df['high'].iloc[i - 2]:
                bull_fvgs.append((float(df['high'].iloc[i - 2]), float(df['low'].iloc[i])))
            if df['high'].iloc[i] < df['low'].iloc[i - 2]:
                bear_fvgs.append((float(df['high'].iloc[i]), float(df['low'].iloc[i - 2])))
        return bull_fvgs[-5:], bear_fvgs[-5:]

    def _order_blocks(self):
        """Detect most recent bullish and bearish order blocks."""
        df = self.df
        bull_ob = bear_ob = None
        for i in range(max(0, len(df) - 20), len(df) - 1):
            # Bullish OB: last bearish candle before price breaks above its high
            if (df['close'].iloc[i] < df['open'].iloc[i] and
                    df['close'].iloc[i + 1] > df['high'].iloc[i]):
                bull_ob = (float(df['low'].iloc[i]), float(df['high'].iloc[i]))
            # Bearish OB: last bullish candle before price breaks below its low
            if (df['close'].iloc[i] > df['open'].iloc[i] and
                    df['close'].iloc[i + 1] < df['low'].iloc[i]):
                bear_ob = (float(df['low'].iloc[i]), float(df['high'].iloc[i]))
        return bull_ob, bear_ob

    def _sr_levels(self) -> dict:
        recent_high = float(self.df['high'].tail(20).max())
        recent_low  = float(self.df['low'].tail(20).min())
        last_close  = float(self.df['close'].iloc[-1])
        pivot = (recent_high + recent_low + last_close) / 3
        r1 = 2 * pivot - recent_low
        r2 = pivot + (recent_high - recent_low)
        s1 = 2 * pivot - recent_high
        s2 = pivot - (recent_high - recent_low)
        return {'resistance': [r1, r2], 'support': [s1, s2], 'pivot': pivot}

    # ── Main signal ──────────────────────────────────────────────────────────

    def generate_signal(self, current_price: float) -> dict:
        atr  = self._atr()
        sr   = self._sr_levels()
        bos  = self._bos_choch()
        fvg_bull, fvg_bear = self._fair_value_gaps()
        bull_ob, bear_ob   = self._order_blocks()

        ema20     = float(self._ema(20).iloc[-1])
        ema50     = float(self._ema(50).iloc[-1])
        rsi_val   = float(self._rsi().iloc[-1])
        macd_line, macd_sig = self._macd()
        macd_val  = float(macd_line.iloc[-1])
        macd_sv   = float(macd_sig.iloc[-1])

        vol_ratio = 1.0
        if 'tick_volume' in self.df.columns:
            avg20 = self.df['tick_volume'].tail(20).mean()
            if avg20 > 0:
                vol_ratio = float(self.df['tick_volume'].tail(5).mean() / avg20)

        bull, bear = 0, 0
        rb, rr_list = [], []   # reason lists

        # EMA trend
        if ema20 > ema50:
            bull += 2; rb.append("EMA20 > EMA50 (uptrend)")
        else:
            bear += 2; rr_list.append("EMA20 < EMA50 (downtrend)")

        # Price vs EMA20
        if current_price > ema20:
            bull += 1; rb.append("Price above EMA20")
        else:
            bear += 1; rr_list.append("Price below EMA20")

        # RSI
        if rsi_val < 35:
            bull += 2; rb.append(f"RSI oversold ({rsi_val:.1f})")
        elif rsi_val > 65:
            bear += 2; rr_list.append(f"RSI overbought ({rsi_val:.1f})")
        elif 42 < rsi_val < 55 and ema20 > ema50:
            bull += 1; rb.append(f"RSI bullish zone ({rsi_val:.1f})")
        elif 45 < rsi_val < 58 and ema20 < ema50:
            bear += 1; rr_list.append(f"RSI bearish zone ({rsi_val:.1f})")

        # MACD
        if macd_val > macd_sv and macd_val > 0:
            bull += 2; rb.append("MACD bullish above zero")
        elif macd_val < macd_sv and macd_val < 0:
            bear += 2; rr_list.append("MACD bearish below zero")
        elif macd_val > macd_sv:
            bull += 1; rb.append("MACD bullish cross")
        elif macd_val < macd_sv:
            bear += 1; rr_list.append("MACD bearish cross")

        # BOS / CHOCH
        if bos['bos_bullish']:
            bull += 3; rb.append("Bullish BOS confirmed")
        if bos['bos_bearish']:
            bear += 3; rr_list.append("Bearish BOS confirmed")
        if bos['choch']:
            bull += 1; rb.append("CHOCH — potential reversal up")

        # Fair Value Gaps
        for fvg_lo, fvg_hi in fvg_bull:
            if fvg_lo <= current_price <= fvg_hi:
                bull += 2; rb.append("Price in bullish FVG"); break
        for fvg_hi, fvg_lo in fvg_bear:
            if fvg_lo <= current_price <= fvg_hi:
                bear += 2; rr_list.append("Price in bearish FVG"); break

        # Order Blocks
        if bull_ob and bull_ob[0] <= current_price <= bull_ob[1]:
            bull += 3; rb.append("Bullish Order Block")
        if bear_ob and bear_ob[0] <= current_price <= bear_ob[1]:
            bear += 3; rr_list.append("Bearish Order Block")

        # S/R proximity (0.1% tolerance)
        tol = current_price * 0.001
        for supp in sr['support']:
            if abs(current_price - supp) < tol:
                bull += 1; rb.append("At pivot support")
        for res in sr['resistance']:
            if abs(current_price - res) < tol:
                bear += 1; rr_list.append("At pivot resistance")

        # Volume amplification
        if vol_ratio > 1.3:
            if bull > bear:
                bull += 1; rb.append(f"High volume ({vol_ratio:.1f}x) — confirms bulls")
            else:
                bear += 1; rr_list.append(f"High volume ({vol_ratio:.1f}x) — confirms bears")

        max_score = 18
        expected_move = atr * 0.4   # ~40 % of ATR as 10-min target

        if bull > bear and bull >= 5:
            sig_type   = 'BUY'
            confidence = min(95, 40 + bull * 4)
            tp1 = current_price + expected_move * 0.5
            tp2 = current_price + expected_move * 1.0
            tp3 = current_price + expected_move * 1.5
            sl  = current_price - expected_move * 0.6
            for res in sorted(sr['resistance']):
                if current_price < res < tp3:
                    tp2 = min(tp2, res)
                    tp3 = min(tp3, res + expected_move * 0.3)
                    break

        elif bear > bull and bear >= 5:
            sig_type   = 'SELL'
            confidence = min(95, 40 + bear * 4)
            tp1 = current_price - expected_move * 0.5
            tp2 = current_price - expected_move * 1.0
            tp3 = current_price - expected_move * 1.5
            sl  = current_price + expected_move * 0.6
            for supp in sorted(sr['support'], reverse=True):
                if current_price > supp > tp3:
                    tp2 = max(tp2, supp)
                    tp3 = max(tp3, supp - expected_move * 0.3)
                    break

        else:
            sig_type   = 'NEUTRAL'
            confidence = 0
            tp1 = tp2 = tp3 = sl = current_price

        return {
            'type':          sig_type,
            'confidence':    confidence,
            'entry':         current_price,
            'tp1': tp1, 'tp2': tp2, 'tp3': tp3,
            'sl':            sl,
            'expected_move': expected_move,
            'bullish_score': bull,
            'bearish_score': bear,
            'max_score':     max_score,
            'reasons_bull':  rb,
            'reasons_bear':  rr_list,
            'indicators': {
                'ema20': ema20, 'ema50': ema50,
                'rsi':   rsi_val,
                'macd':  macd_val, 'macd_signal': macd_sv,
                'vol_ratio': vol_ratio,
            },
            'sr_levels': sr,
            'bos':       bos,
            'atr':       atr,
        }


# ══════════════════════════════════════════════════════════════════════════════
# AUTO TRADER — MT5 order management
# ══════════════════════════════════════════════════════════════════════════════
class AutoTrader:
    MAGIC = 234567

    def _lot_size(self, symbol: str, sl_dist: float, risk_pct: float, balance: float) -> float:
        try:
            info = mt5.symbol_info(symbol)
            if not info or info.trade_tick_size == 0 or sl_dist == 0:
                return info.volume_min if info else 0.01
            risk_money = balance * (risk_pct / 100)
            pips_risk  = sl_dist / info.trade_tick_size
            lot = risk_money / (pips_risk * info.trade_tick_value)
            lot = round(lot / info.volume_step) * info.volume_step
            return float(np.clip(lot, info.volume_min, info.volume_max))
        except Exception:
            return 0.01

    @staticmethod
    def market_status(symbol: str) -> tuple:
        """Return (is_open: bool, mode_label: str).

        trade_mode values:
          0 = DISABLED, 1 = LONGONLY, 2 = SHORTONLY, 3 = CLOSEONLY, 4 = FULL
        """
        info = mt5.symbol_info(symbol)
        if not info:
            return False, "UNKNOWN"
        mode = info.trade_mode
        labels = {0: "DISABLED", 1: "LONG ONLY", 2: "SHORT ONLY",
                  3: "CLOSE ONLY", 4: "OPEN"}
        is_open = mode == mt5.SYMBOL_TRADE_MODE_FULL
        return is_open, labels.get(mode, str(mode))

    @staticmethod
    def _algo_trading_enabled(symbol: str = ""):
        """Check terminal, account, and market-open flags."""
        term = mt5.terminal_info()
        if term and not term.trade_allowed:
            return False, ("Algo Trading is OFF in the MT5 terminal. "
                           "Enable the 'Algo Trading' button in the toolbar, or go to "
                           "Tools → Options → Expert Advisors → Allow Algo Trading.")
        acct = mt5.account_info()
        if acct and not acct.trade_expert:
            return False, ("Broker/server has disabled AutoTrading for this account "
                           "(error 10027). Use a demo account that supports EAs, "
                           "or contact your broker to enable algorithmic trading.")
        if symbol:
            info = mt5.symbol_info(symbol)
            if info and info.trade_mode != mt5.SYMBOL_TRADE_MODE_FULL:
                labels = {0: "disabled", 1: "long-only", 2: "short-only", 3: "close-only"}
                mode = labels.get(info.trade_mode, f"mode {info.trade_mode}")
                return False, (f"Market is closed or restricted for {symbol} "
                               f"(trading {mode}). Wait for the market to open.")
        return True, ""

    def place_order(self, symbol: str, signal: dict, risk_pct: float, tp_target: str = 'TP2'):
        try:
            ok, reason = self._algo_trading_enabled(symbol)
            if not ok:
                return None, reason

            acct = mt5.account_info()
            if not acct:
                return None, "Cannot get account"

            tp_price = signal[tp_target.lower()]
            sl_dist  = abs(signal['entry'] - signal['sl'])
            lot      = self._lot_size(symbol, sl_dist, risk_pct, acct.balance)

            is_buy     = signal['type'] == 'BUY'
            order_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL
            tick       = mt5.symbol_info_tick(symbol)
            price      = tick.ask if is_buy else tick.bid
            sym_info   = mt5.symbol_info(symbol)
            d          = sym_info.digits if sym_info else 5

            base_request = {
                "action":    mt5.TRADE_ACTION_DEAL,
                "symbol":    symbol,
                "volume":    lot,
                "type":      order_type,
                "price":     price,
                "sl":        round(signal['sl'],  d),
                "tp":        round(tp_price,      d),
                "deviation": 20,
                "magic":     self.MAGIC,
                "comment":   "SMC Auto",
                "type_time": mt5.ORDER_TIME_GTC,
            }
            # Try all filling modes — brokers differ on which they accept
            for filling in (mt5.ORDER_FILLING_RETURN,
                            mt5.ORDER_FILLING_FOK,
                            mt5.ORDER_FILLING_IOC):
                req = {**base_request, "type_filling": filling}
                result = mt5.order_send(req)
                if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                    return result.order, None
                # Only retry on filling-mode errors; stop on hard errors
                if result and result.retcode not in (
                        10014,  # INVALID
                        10030,  # INVALID_FILL
                ):
                    break

            code = result.retcode if result else "N/A"
            _RETCODE_HINTS = {
                10027: ("Server disabled AutoTrading (10027). Enable Algo Trading in the "
                        "MT5 toolbar and verify your account type supports EAs."),
                10028: ("Client disabled AutoTrading (10028). Click the 'Algo Trading' "
                        "button in the MT5 toolbar to enable it."),
                10018: "Trading is disabled for this symbol (market may be closed).",
                10019: "Market is closed.",
                10020: "Not enough money.",
                10017: "Invalid stops — SL/TP too close to price (check symbol min distance).",
            }
            msg = _RETCODE_HINTS.get(code, f"MT5 error {code}")
            return None, msg
        except Exception as e:
            return None, str(e)

    def get_open_positions(self):
        try:
            pos = mt5.positions_get()
            return [p for p in pos if p.magic == self.MAGIC] if pos else []
        except Exception:
            return []

    def close_position(self, ticket: int):
        try:
            pos = mt5.positions_get(ticket=ticket)
            if not pos:
                return False, "Not found"
            p          = pos[0]
            order_type = mt5.ORDER_TYPE_SELL if p.type == 0 else mt5.ORDER_TYPE_BUY
            tick       = mt5.symbol_info_tick(p.symbol)
            price      = tick.bid if p.type == 0 else tick.ask
            base = {
                "action":    mt5.TRADE_ACTION_DEAL,
                "symbol":    p.symbol,
                "volume":    p.volume,
                "type":      order_type,
                "position":  ticket,
                "price":     price,
                "deviation": 20,
                "magic":     self.MAGIC,
                "comment":   "SMC Close",
                "type_time": mt5.ORDER_TIME_GTC,
            }
            for filling in (mt5.ORDER_FILLING_RETURN,
                            mt5.ORDER_FILLING_FOK,
                            mt5.ORDER_FILLING_IOC):
                result = mt5.order_send({**base, "type_filling": filling})
                if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                    return True, result.retcode
                if result and result.retcode not in (10014, 10030):
                    break
            return False, getattr(result, 'retcode', 'N/A')
        except Exception as e:
            return False, str(e)

    def fetch_closed_deals(self, from_dt=None):
        """Pull closed deals from MT5 history filtered by magic number."""
        try:
            start = from_dt or (datetime.now() - timedelta(days=30))
            deals = mt5.history_deals_get(start, datetime.now())
            if not deals:
                return []
            rows = []
            for d in deals:
                if d.magic != self.MAGIC or d.entry != mt5.DEAL_ENTRY_OUT:
                    continue
                rows.append({
                    "Date":        datetime.fromtimestamp(d.time).strftime('%Y-%m-%d'),
                    "Time":        datetime.fromtimestamp(d.time).strftime('%H:%M:%S'),
                    "Pair":        d.symbol,
                    "Type":        "BUY" if d.type == mt5.DEAL_TYPE_BUY else "SELL",
                    "Lot":         d.volume,
                    "Entry":       "",
                    "SL":          "",
                    "TP":          "",
                    "Confidence":  "",
                    "Ticket":      d.position_id,
                    "Close_Price": d.price,
                    "PnL":         round(d.profit, 2),
                    "Status":      "WIN" if d.profit >= 0 else "LOSS",
                    "Source":      "MT5_HISTORY",
                })
            return rows
        except Exception:
            return []


# ══════════════════════════════════════════════════════════════════════════════
# MT5 DATA HANDLER
# ══════════════════════════════════════════════════════════════════════════════
class RealMT5Data:
    SYMBOLS = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD",
               "USDCAD", "BTCUSD", "NZDUSD", "USDCHF"]

    def __init__(self):
        self.connected = False
        self.symbols   = self.SYMBOLS

    def connect(self) -> bool:
        try:
            mt5_path = None
            if sys.platform == "win32":
                for path in [
                    "C:\\Program Files\\MetaTrader 5\\terminal64.exe",
                    "C:\\Program Files (x86)\\MetaTrader 5\\terminal.exe",
                    os.path.expanduser("~\\AppData\\Local\\Programs\\MetaTrader 5\\terminal64.exe"),
                ]:
                    if os.path.exists(path):
                        mt5_path = path
                        break
            ok = mt5.initialize(mt5_path) if mt5_path else mt5.initialize()
            if not ok:
                st.error(f"MT5 init failed: {mt5.last_error()}")
                return False
            self.connected = True
            for s in self.symbols:
                mt5.symbol_select(s, True)
            return True
        except Exception as e:
            st.error(f"MT5 error: {e}")
            return False

    def disconnect(self):
        if self.connected:
            mt5.shutdown()
            self.connected = False

    def get_tick(self, symbol: str):
        try:
            t = mt5.symbol_info_tick(symbol)
            if t:
                return {'bid': t.bid, 'ask': t.ask,
                        'spread': t.ask - t.bid,
                        'volume': t.volume,
                        'time': datetime.fromtimestamp(t.time)}
        except Exception:
            pass
        return None

    def get_rates(self, symbol: str, timeframe=mt5.TIMEFRAME_M5, count: int = 200):
        try:
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
            if rates is not None and len(rates) > 0:
                df = pd.DataFrame(rates)
                df['time'] = pd.to_datetime(df['time'], unit='s')
                return df
        except Exception:
            pass
        return None

    def get_symbol_info(self, symbol: str):
        try:
            info = mt5.symbol_info(symbol)
            if info:
                return {'name': info.name, 'digits': info.digits,
                        'point': info.point, 'description': info.description}
        except Exception:
            pass
        return None


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════
_TF_MAP = {
    "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15, "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4, "D1": mt5.TIMEFRAME_D1,
}

def get_timeframe(tf: str):
    return _TF_MAP.get(tf, mt5.TIMEFRAME_M5)

def pip_mult(pair: str) -> int:
    return 100 if "JPY" in pair else 10000

def to_pips(value: float, pair: str) -> str:
    return f"{value * pip_mult(pair):.1f}"

def init_mt5():
    if st.session_state.mt5_data is None:
        d = RealMT5Data()
        if d.connect():
            st.session_state.mt5_data = d
    return st.session_state.mt5_data

def generate_new_signal(mt5_data, pair: str, timeframe: str, digits: int):
    df = mt5_data.get_rates(pair, get_timeframe(timeframe), 200)
    if df is None or len(df) < 60:
        return None
    tick = mt5_data.get_tick(pair)
    if not tick:
        return None
    price     = (tick['bid'] + tick['ask']) / 2
    predictor = SMCPredictor(df, digits, pair)
    signal    = predictor.generate_signal(price)
    now = datetime.now()
    st.session_state.current_signal        = signal
    st.session_state.signal_generated_time = now
    st.session_state.signal_valid_until    = now + timedelta(minutes=10)
    st.session_state.next_signal_time      = now + timedelta(minutes=20)
    st.session_state.price_at_signal       = price
    return signal


# ══════════════════════════════════════════════════════════════════════════════
# UI — SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
st.title("📈 SMC Auto Trader")
st.markdown("**Multi-indicator Smart Money Concepts · EMA · RSI · MACD · BOS · FVG · Order Blocks · Auto Execution**")

auto_trader = AutoTrader()

with st.sidebar:
    st.markdown("## 🔌 MT5 Connection")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔌 Connect", use_container_width=True):
            with st.spinner("Connecting…"):
                d = init_mt5()
                if d and d.connected:
                    st.session_state.mt5_initialized = True
                    info   = d.get_symbol_info(st.session_state.selected_pair)
                    digits = info['digits'] if info else 5
                    generate_new_signal(d, st.session_state.selected_pair,
                                        st.session_state.timeframe, digits)
                    st.success("Connected!")
                    time.sleep(0.5)
                    st.rerun()
    with c2:
        if st.button("❌ Disconnect", use_container_width=True):
            if st.session_state.mt5_data:
                st.session_state.mt5_data.disconnect()
                st.session_state.mt5_data = None
            st.session_state.mt5_initialized  = False
            st.session_state.current_signal   = None
            st.session_state.auto_trade_enabled = False
            st.rerun()

    mt5_data = st.session_state.mt5_data if st.session_state.mt5_initialized else None

    if mt5_data and mt5_data.connected:
        st.markdown("**Status:** <span class='status-connected'>● CONNECTED</span>",
                    unsafe_allow_html=True)
        acct = mt5.account_info()
        if acct:
            st.markdown("---")
            st.markdown("### 💼 Account")
            ca, cb = st.columns(2)
            ca.metric("Balance",  f"${acct.balance:,.0f}")
            cb.metric("Equity",   f"${acct.equity:,.0f}")
            pcolor = "green" if acct.profit >= 0 else "red"
            st.markdown(
                f"Open P&L: <span style='color:{pcolor};font-weight:bold'>"
                f"${acct.profit:+.2f}</span>", unsafe_allow_html=True)
    else:
        st.markdown("**Status:** <span class='status-disconnected'>● DISCONNECTED</span>",
                    unsafe_allow_html=True)
        st.info("Click Connect to start")

    st.markdown("---")

    if mt5_data and mt5_data.connected:
        available = [s for s in mt5_data.symbols if mt5.symbol_info(s)]
        if available:
            new_pair = st.selectbox(
                "Symbol", available,
                index=available.index(st.session_state.selected_pair)
                      if st.session_state.selected_pair in available else 0)
            if new_pair != st.session_state.selected_pair:
                st.session_state.selected_pair = new_pair
                info   = mt5_data.get_symbol_info(new_pair)
                digits = info['digits'] if info else 5
                generate_new_signal(mt5_data, new_pair, st.session_state.timeframe, digits)
                st.rerun()

        st.session_state.timeframe = st.selectbox(
            "Timeframe", ["M1", "M5", "M15", "M30", "H1"], index=1)

        # Signal timers
        st.markdown("---")
        st.markdown("### ⏰ Signal Timers")
        if st.session_state.signal_valid_until:
            rem = (st.session_state.signal_valid_until - datetime.now()).total_seconds()
            if rem > 0:
                st.markdown(
                    f"<div class='timer-box'><div class='price-label'>SIGNAL VALID FOR</div>"
                    f"<div class='timer-value'>{int(rem//60):02d}:{int(rem%60):02d}</div></div>",
                    unsafe_allow_html=True)
            else:
                st.warning("Signal expired — next signal pending")

        if st.session_state.next_signal_time:
            nxt = (st.session_state.next_signal_time - datetime.now()).total_seconds()
            if nxt > 0:
                st.markdown(
                    f"<div class='timer-box'><div class='price-label'>NEXT SIGNAL IN</div>"
                    f"<div class='timer-value'>{int(nxt//60):02d}:{int(nxt%60):02d}</div></div>",
                    unsafe_allow_html=True)

        # Auto trading controls
        st.markdown("---")
        st.markdown("### 🤖 Auto Trading")
        enabled = st.toggle("Enable Auto Trading",
                             value=st.session_state.auto_trade_enabled)
        st.session_state.auto_trade_enabled = enabled
        st.markdown(
            f"<div class='{'at-on' if enabled else 'at-off'}'>"
            f"{'🟢 AUTO TRADE ON' if enabled else '🔴 AUTO TRADE OFF'}</div>",
            unsafe_allow_html=True)

        st.session_state.auto_trade_risk_pct = st.number_input(
            "Risk per trade (%)", 0.1, 5.0,
            value=st.session_state.auto_trade_risk_pct, step=0.1)

        st.session_state.auto_trade_tp = st.selectbox(
            "Target TP level", ["TP1", "TP2", "TP3"],
            index=["TP1", "TP2", "TP3"].index(st.session_state.auto_trade_tp))

        st.session_state.auto_trade_min_conf = st.slider(
            "Min confidence to trade", 50, 90,
            value=st.session_state.auto_trade_min_conf)

        if st.button("🚫 Close ALL Positions", use_container_width=True):
            positions = auto_trader.get_open_positions()
            closed = 0
            for p in positions:
                ok, _ = auto_trader.close_position(p.ticket)
                if ok:
                    closed += 1
            st.success(f"Closed {closed}/{len(positions)} position(s)")
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN CONTENT
# ══════════════════════════════════════════════════════════════════════════════
mt5_data = st.session_state.mt5_data if st.session_state.mt5_initialized else None

if not (mt5_data and mt5_data.connected and st.session_state.selected_pair):
    st.info("🔌 Connect to MT5 to start receiving signals and auto trading.")
    with st.expander("How It Works", expanded=True):
        st.markdown("""
**Signal Engine (multi-factor confluence, max score 18):**
| Factor | Max pts |
|---|---|
| EMA 20/50 trend + price vs EMA | 3 |
| RSI overbought/oversold | 2 |
| MACD crossover (above/below zero) | 2 |
| Break of Structure (BOS) | 3 |
| Fair Value Gap entry | 2 |
| Order Block touch | 3 |
| S/R pivot proximity | 2 |
| Volume confirmation | 1 |

A BUY or SELL signal fires when one side scores **≥ 5** and exceeds the other.

**Auto Trading:**
- Enable in sidebar → set risk % and minimum confidence
- One position open at a time per symbol (deduplication by signal timestamp)
- Manual "Place Order" button available on every signal card
- Emergency "Close All Positions" button in sidebar
        """)
    st.stop()

# ── Fetch live data ───────────────────────────────────────────────────────────
sym_info = mt5_data.get_symbol_info(st.session_state.selected_pair)
digits   = sym_info['digits'] if sym_info else 5
tick     = mt5_data.get_tick(st.session_state.selected_pair)

if not tick:
    st.error("Cannot get tick data. Check MT5 connection.")
    if st.session_state.auto_refresh:
        time.sleep(st.session_state.refresh_rate)
        st.rerun()
    st.stop()

# ── Market open/closed status ─────────────────────────────────────────────────
market_open, market_mode = auto_trader.market_status(st.session_state.selected_pair)
if not market_open:
    st.warning(
        f"⚠️ **Market is {market_mode}** for {st.session_state.selected_pair}. "
        "Charts and signals still update — auto/manual trading is blocked until the market opens.",
        icon=None)

# ── Signal generation / refresh ───────────────────────────────────────────────
if (st.session_state.next_signal_time and
        datetime.now() >= st.session_state.next_signal_time):
    generate_new_signal(mt5_data, st.session_state.selected_pair,
                        st.session_state.timeframe, digits)
    st.rerun()

if st.session_state.current_signal is None:
    generate_new_signal(mt5_data, st.session_state.selected_pair,
                        st.session_state.timeframe, digits)

signal = st.session_state.current_signal

# ── Auto trade execution ──────────────────────────────────────────────────────
min_conf = st.session_state.auto_trade_min_conf
if (market_open and
        st.session_state.auto_trade_enabled and signal and
        signal['type'] in ('BUY', 'SELL') and
        signal['confidence'] >= min_conf):
    sig_id = st.session_state.signal_generated_time
    if sig_id != st.session_state.last_auto_trade_signal:
        open_pos = auto_trader.get_open_positions()
        same_sym = [p for p in open_pos if p.symbol == st.session_state.selected_pair]
        if not same_sym:
            ticket, err = auto_trader.place_order(
                st.session_state.selected_pair, signal,
                st.session_state.auto_trade_risk_pct,
                st.session_state.auto_trade_tp)
            st.session_state.last_auto_trade_signal = sig_id
            if ticket:
                _rec = {
                    'Date':        datetime.now().strftime('%Y-%m-%d'),
                    'Time':        datetime.now().strftime('%H:%M:%S'),
                    'Pair':        st.session_state.selected_pair,
                    'Type':        signal['type'],
                    'Lot':         '',
                    'Entry':       round(signal['entry'], digits),
                    'SL':          round(signal['sl'], digits),
                    'TP':          round(signal[st.session_state.auto_trade_tp.lower()], digits),
                    'Confidence':  f"{signal['confidence']:.0f}%",
                    'Ticket':      ticket,
                    'Close_Price': '',
                    'PnL':         '',
                    'Status':      'OPEN',
                    'Source':      'AUTO',
                }
                st.session_state.trade_history.append(_rec)
                _append_log(_rec)
                st.toast(f"✅ {signal['type']} #{ticket} placed on {st.session_state.selected_pair}")
            else:
                st.toast(f"⚠️ Auto-trade failed: {err}", icon="⚠️")

# ── Price bar ─────────────────────────────────────────────────────────────────
current_price = (tick['bid'] + tick['ask']) / 2
spread_pips   = tick['spread'] * pip_mult(st.session_state.selected_pair)
mkt_color     = "#28a745" if market_open else "#dc3545"
mkt_icon      = "●" if market_open else "●"

col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.markdown(
    f"<div class='price-card bid-card'><div class='price-label'>BID</div>"
    f"<div class='price-value'>{tick['bid']:.{digits}f}</div></div>",
    unsafe_allow_html=True)
col2.markdown(
    f"<div class='price-card ask-card'><div class='price-label'>ASK</div>"
    f"<div class='price-value'>{tick['ask']:.{digits}f}</div></div>",
    unsafe_allow_html=True)
col3.markdown(
    f"<div class='price-card'><div class='price-label'>SPREAD</div>"
    f"<div class='spread-value'>{spread_pips:.1f} pips</div></div>",
    unsafe_allow_html=True)
col4.markdown(
    f"<div class='price-card'><div class='price-label'>VOLUME</div>"
    f"<div class='price-value' style='font-size:20px'>{tick['volume']:,}</div></div>",
    unsafe_allow_html=True)
col5.markdown(
    f"<div class='price-card'><div class='price-label'>UPDATED</div>"
    f"<div class='price-value' style='font-size:14px'>{tick['time'].strftime('%H:%M:%S')}</div></div>",
    unsafe_allow_html=True)
col6.markdown(
    f"<div class='price-card'><div class='price-label'>MARKET</div>"
    f"<div class='price-value' style='font-size:16px;color:{mkt_color}'>"
    f"{mkt_icon} {market_mode}</div></div>",
    unsafe_allow_html=True)

# ── Open positions ─────────────────────────────────────────────────────────────
open_positions = auto_trader.get_open_positions()
if open_positions:
    st.markdown("---")
    st.markdown("### 📂 Open Positions")
    rows = []
    for p in open_positions:
        rows.append({
            'Ticket':     p.ticket,
            'Symbol':     p.symbol,
            'Type':       'BUY' if p.type == 0 else 'SELL',
            'Volume':     p.volume,
            'Open':       round(p.price_open,    digits),
            'Current':    round(p.price_current, digits),
            'SL':         round(p.sl, digits),
            'TP':         round(p.tp, digits),
            'P&L ($)':    round(p.profit, 2),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    close_cols = st.columns(min(len(open_positions), 4))
    for i, p in enumerate(open_positions[:4]):
        if close_cols[i].button(f"Close #{p.ticket}", key=f"close_{p.ticket}"):
            ok, msg = auto_trader.close_position(p.ticket)
            st.toast("✅ Closed" if ok else f"⚠️ {msg}")
            st.rerun()

# ── Signal card ───────────────────────────────────────────────────────────────
if signal:
    st.markdown("---")
    st.markdown("## 🎯 Active Signal")

    if signal['type'] in ('BUY', 'SELL'):
        is_buy  = signal['type'] == 'BUY'
        css_cls = 'signal-buy' if is_buy else 'signal-sell'
        icon    = '🟢' if is_buy else '🔴'
        risk    = abs(signal['entry'] - signal['sl'])
        reward  = abs(signal['tp2']   - signal['entry'])
        rr      = reward / risk if risk > 0 else 0

        reasons  = signal['reasons_bull'] if is_buy else signal['reasons_bear']
        reasons_html = "".join(f"<li>{r}</li>" for r in reasons)
        ind = signal['indicators']
        score = signal['bullish_score'] if is_buy else signal['bearish_score']

        col_sig, col_meta = st.columns([3, 1])
        with col_sig:
            st.markdown(f"""
            <div class='{css_cls}'>
                <h2>{icon} {signal['type']} &nbsp;|&nbsp; Confidence {signal['confidence']:.0f}%
                    &nbsp;|&nbsp; Score {score}/{signal['max_score']}</h2>
                <div style='display:flex;gap:40px;flex-wrap:wrap'>
                    <div>
                        <h4>Levels</h4>
                        <p><strong>Entry:</strong> {signal['entry']:.{digits}f}</p>
                        <p><strong>TP1:</strong> {signal['tp1']:.{digits}f}
                           &nbsp;|&nbsp;<strong>TP2:</strong> {signal['tp2']:.{digits}f}
                           &nbsp;|&nbsp;<strong>TP3:</strong> {signal['tp3']:.{digits}f}</p>
                        <p><strong>SL:</strong> {signal['sl']:.{digits}f}</p>
                        <p><strong>Expected move:</strong>
                           {signal['expected_move']:.{digits}f}
                           ({to_pips(signal['expected_move'], st.session_state.selected_pair)} pips)</p>
                        <p><strong>ATR:</strong> {signal['atr']:.{digits}f}
                           ({to_pips(signal['atr'], st.session_state.selected_pair)} pips)</p>
                    </div>
                    <div>
                        <h4>Indicators</h4>
                        <p>EMA20: {ind['ema20']:.{digits}f} &nbsp;|&nbsp; EMA50: {ind['ema50']:.{digits}f}</p>
                        <p>RSI: {ind['rsi']:.1f} &nbsp;|&nbsp; MACD: {ind['macd']:+.5f}</p>
                        <p>Volume ratio: {ind['vol_ratio']:.2f}x</p>
                        <p>BOS ↑: {'✅' if signal['bos']['bos_bullish'] else '—'}
                           &nbsp; BOS ↓: {'✅' if signal['bos']['bos_bearish'] else '—'}
                           &nbsp; CHOCH: {'✅' if signal['bos']['choch'] else '—'}</p>
                    </div>
                </div>
                <hr>
                <h4>Confluence factors:</h4>
                <ul>{reasons_html}</ul>
            </div>
            """, unsafe_allow_html=True)

        with col_meta:
            stars = "⭐" * min(5, score // 2)
            st.markdown(f"""
            <div class='price-card'>
                <div class='price-label'>RISK / REWARD</div>
                <div class='price-value'>1:{rr:.2f}</div>
                <hr>
                <div class='price-label'>CONFLUENCE</div>
                <div style='font-size:20px'>{stars}</div>
                <hr>
                <div class='price-label'>SCORE</div>
                <div class='price-value' style='font-size:22px'>{score}/{signal['max_score']}</div>
            </div>
            """, unsafe_allow_html=True)

            if not market_open:
                st.warning(f"Market {market_mode}", icon="🔒")
            if st.button(f"▶ Manual {signal['type']}",
                         use_container_width=True, key="manual_trade",
                         disabled=not market_open):
                ticket, err = auto_trader.place_order(
                    st.session_state.selected_pair, signal,
                    st.session_state.auto_trade_risk_pct,
                    st.session_state.auto_trade_tp)
                if ticket:
                    st.success(f"Order #{ticket} placed")
                    st.session_state.last_auto_trade_signal = \
                        st.session_state.signal_generated_time
                    _rec = {
                        'Date':        datetime.now().strftime('%Y-%m-%d'),
                        'Time':        datetime.now().strftime('%H:%M:%S'),
                        'Pair':        st.session_state.selected_pair,
                        'Type':        signal['type'],
                        'Lot':         '',
                        'Entry':       round(signal['entry'], digits),
                        'SL':          round(signal['sl'], digits),
                        'TP':          round(signal[st.session_state.auto_trade_tp.lower()], digits),
                        'Confidence':  f"{signal['confidence']:.0f}%",
                        'Ticket':      ticket,
                        'Close_Price': '',
                        'PnL':         '',
                        'Status':      'MANUAL',
                        'Source':      'MANUAL',
                    }
                    st.session_state.trade_history.append(_rec)
                    _append_log(_rec)
                else:
                    st.error(f"Failed: {err}")

    else:
        ind = signal['indicators']
        st.markdown(f"""
        <div class='signal-neutral'>
            <h2>🟡 NEUTRAL — No confirmed setup</h2>
            <p>Bull score: <strong>{signal['bullish_score']}</strong>
               &nbsp;|&nbsp; Bear score: <strong>{signal['bearish_score']}</strong>
               &nbsp;|&nbsp; Required: ≥ 5</p>
            <p>RSI: {ind['rsi']:.1f} &nbsp;|&nbsp;
               Trend: {'↑ UP' if ind['ema20'] > ind['ema50'] else '↓ DOWN'} &nbsp;|&nbsp;
               Vol ratio: {ind['vol_ratio']:.2f}x</p>
            <p>Wait for stronger confluence or the next signal cycle.</p>
        </div>
        """, unsafe_allow_html=True)

# ── Chart ─────────────────────────────────────────────────────────────────────
hist = mt5_data.get_rates(st.session_state.selected_pair,
                           get_timeframe(st.session_state.timeframe), 200)
if hist is not None:
    st.markdown("---")
    st.markdown("### 📊 Chart")

    ema20_s = hist['close'].ewm(span=20, adjust=False).mean()
    ema50_s = hist['close'].ewm(span=50, adjust=False).mean()

    # RSI subplot
    rsi_delta = hist['close'].diff()
    rsi_gain  = rsi_delta.clip(lower=0).rolling(14).mean()
    rsi_loss  = (-rsi_delta.clip(upper=0)).rolling(14).mean()
    rsi_s     = 100 - (100 / (1 + rsi_gain / rsi_loss.replace(0, np.nan)))

    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        row_heights=[0.60, 0.20, 0.20],
        vertical_spacing=0.03,
        subplot_titles=("Price", "Volume", "RSI(14)"))

    # Candles
    fig.add_trace(go.Candlestick(
        x=hist['time'], open=hist['open'], high=hist['high'],
        low=hist['low'], close=hist['close'],
        name=st.session_state.selected_pair,
        increasing_line_color='#28a745',
        decreasing_line_color='#dc3545'), row=1, col=1)

    fig.add_trace(go.Scatter(x=hist['time'], y=ema20_s, name='EMA20',
        line=dict(color='#007bff', width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=hist['time'], y=ema50_s, name='EMA50',
        line=dict(color='#ff7f0e', width=1.5, dash='dash')), row=1, col=1)

    # Signal levels
    if signal and signal['type'] != 'NEUTRAL':
        for lvl, lbl, col, dsh in [
            (signal['entry'], 'ENTRY', '#ffc107', 'solid'),
            (signal['sl'],    'SL',    '#dc3545', 'dot'),
            (signal['tp1'],   'TP1',   '#28a745', 'dot'),
            (signal['tp2'],   'TP2',   '#28a745', 'dash'),
            (signal['tp3'],   'TP3',   '#28a745', 'dashdot'),
        ]:
            fig.add_hline(y=lvl, line_color=col, line_dash=dsh, line_width=1.5,
                          annotation_text=lbl, annotation_position="right",
                          row=1, col=1)

    # Volume
    if 'tick_volume' in hist.columns:
        bar_colors = ['#28a745' if c >= o else '#dc3545'
                      for c, o in zip(hist['close'], hist['open'])]
        fig.add_trace(go.Bar(x=hist['time'], y=hist['tick_volume'],
            name='Volume', marker_color=bar_colors, opacity=0.7), row=2, col=1)

    # RSI
    fig.add_trace(go.Scatter(x=hist['time'], y=rsi_s, name='RSI',
        line=dict(color='#9b59b6', width=1.5)), row=3, col=1)
    fig.add_hline(y=70, line_color='#dc3545', line_dash='dot', line_width=1, row=3, col=1)
    fig.add_hline(y=30, line_color='#28a745', line_dash='dot', line_width=1, row=3, col=1)
    fig.add_hrect(y0=30, y1=70, fillcolor='#f0f0f0', opacity=0.2,
                  line_width=0, row=3, col=1)

    fig.update_layout(
        template='plotly_white',
        title=f"{st.session_state.selected_pair} — {st.session_state.timeframe}",
        height=650,
        margin=dict(l=50, r=80, t=60, b=30),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation='h', y=1.04),
    )
    fig.update_xaxes(gridcolor='#e9ecef')
    fig.update_yaxes(gridcolor='#e9ecef')
    st.plotly_chart(fig, use_container_width=True)

# ── Trade Log ─────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("## 📋 Trade Log")

log_tab, stats_tab, hist_tab = st.tabs(["Session Log", "Statistics", "MT5 History (30d)"])

with log_tab:
    records = _load_log()  # always read fresh from disk
    if records:
        log_df = pd.DataFrame(records)

        # Sync OPEN positions against current MT5 positions to update P&L
        if mt5_data and mt5_data.connected:
            live_pos = {str(p.ticket): p for p in auto_trader.get_open_positions()}
            updated = False
            for row in records:
                if row.get('Status') == 'OPEN' and str(row.get('Ticket')) in live_pos:
                    pos = live_pos[str(row['Ticket'])]
                    row['PnL'] = round(pos.profit, 2)
                    row['Close_Price'] = round(pos.price_current, digits)
                elif row.get('Status') == 'OPEN' and str(row.get('Ticket')) not in live_pos:
                    # Position closed since last reload — mark as done
                    row['Status'] = 'CLOSED'
                    updated = True
            if updated:
                _save_log(records)
                st.session_state.trade_history = records
            log_df = pd.DataFrame(records)

        # Color-code rows by status
        def _row_style(row):
            if row.get('Status') == 'WIN':
                return ['background-color:#d4edda'] * len(row)
            if row.get('Status') == 'LOSS':
                return ['background-color:#f8d7da'] * len(row)
            if row.get('Status') == 'OPEN':
                return ['background-color:#fff3cd'] * len(row)
            return [''] * len(row)

        st.dataframe(
            log_df.style.apply(_row_style, axis=1),
            use_container_width=True, hide_index=True)

        dl_col, clr_col = st.columns(2)
        with dl_col:
            csv_bytes = log_df.to_csv(index=False).encode()
            st.download_button("⬇ Export CSV", csv_bytes,
                               file_name=f"trade_log_{datetime.now().strftime('%Y%m%d')}.csv",
                               mime='text/csv', use_container_width=True)
        with clr_col:
            if st.button("🗑 Clear Log", use_container_width=True):
                _save_log([])
                st.session_state.trade_history = []
                st.rerun()
    else:
        st.info("No trades logged yet. Place a trade (manual or auto) to start the log.")

with stats_tab:
    records = _load_log()
    if records:
        df_s = pd.DataFrame(records)
        closed = df_s[df_s['Status'].isin(['WIN', 'LOSS', 'CLOSED'])]
        wins   = df_s[df_s['Status'] == 'WIN']
        losses = df_s[df_s['Status'] == 'LOSS']

        def _safe_pnl(df):
            try:
                return df['PnL'].astype(float).sum()
            except Exception:
                return 0.0

        total_trades  = len(closed)
        total_pnl     = _safe_pnl(closed)
        win_pnl       = _safe_pnl(wins)
        loss_pnl      = _safe_pnl(losses)
        win_rate      = (len(wins) / total_trades * 100) if total_trades else 0
        avg_win       = (win_pnl  / len(wins))   if len(wins)   else 0
        avg_loss      = (loss_pnl / len(losses))  if len(losses) else 0
        profit_factor = (win_pnl / abs(loss_pnl)) if loss_pnl else float('inf')

        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Total Trades",  total_trades)
        r2.metric("Win Rate",      f"{win_rate:.1f}%")
        r3.metric("Total P&L",     f"${total_pnl:+.2f}")
        r4.metric("Profit Factor", f"{profit_factor:.2f}" if profit_factor != float('inf') else "∞")

        r5, r6, r7, r8 = st.columns(4)
        r5.metric("Wins",     len(wins))
        r6.metric("Losses",   len(losses))
        r7.metric("Avg Win",  f"${avg_win:+.2f}")
        r8.metric("Avg Loss", f"${avg_loss:+.2f}")

        # Equity curve from P&L column
        try:
            pnl_vals = closed['PnL'].astype(float).reset_index(drop=True)
            if not pnl_vals.empty:
                equity = pnl_vals.cumsum()
                fig_eq = go.Figure(go.Scatter(
                    y=equity, mode='lines+markers',
                    line=dict(color='#007bff', width=2),
                    fill='tozeroy',
                    fillcolor='rgba(0,123,255,0.1)',
                    name='Cumulative P&L'))
                fig_eq.update_layout(
                    title='Equity Curve (closed trades)',
                    template='plotly_white', height=300,
                    margin=dict(l=40, r=20, t=40, b=30),
                    yaxis_title='Cumulative P&L ($)')
                st.plotly_chart(fig_eq, use_container_width=True)
        except Exception:
            pass

        # By pair breakdown
        try:
            by_pair = (closed.assign(PnL=closed['PnL'].astype(float))
                             .groupby('Pair')
                             .agg(Trades=('Ticket', 'count'),
                                  PnL=('PnL', 'sum'))
                             .reset_index()
                             .sort_values('PnL', ascending=False))
            st.dataframe(by_pair, use_container_width=True, hide_index=True)
        except Exception:
            pass
    else:
        st.info("No closed trades yet — statistics will appear here once trades close.")

with hist_tab:
    if mt5_data and mt5_data.connected:
        with st.spinner("Loading MT5 deal history…"):
            hist_rows = auto_trader.fetch_closed_deals()
        if hist_rows:
            hist_df = pd.DataFrame(hist_rows)
            pnl_sum = hist_df['PnL'].sum()
            wins_h  = (hist_df['PnL'] >= 0).sum()
            losses_h= (hist_df['PnL'] <  0).sum()
            h1, h2, h3 = st.columns(3)
            h1.metric("Closed Deals (30d)", len(hist_df))
            h2.metric("Win / Loss", f"{wins_h} / {losses_h}")
            h3.metric("Total P&L",  f"${pnl_sum:+.2f}")
            st.dataframe(hist_df, use_container_width=True, hide_index=True)
        else:
            st.info("No closed deals found for this account in the last 30 days.")
    else:
        st.info("Connect to MT5 to view deal history.")

# ── Footer + auto-refresh ─────────────────────────────────────────────────────
st.markdown("---")
at_status = "🟢 ON" if st.session_state.auto_trade_enabled else "🔴 OFF"
st.caption(
    f"SMC Auto Trader | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
    f"Auto-trade: {at_status} | Risk: {st.session_state.auto_trade_risk_pct}% | "
    f"Min confidence: {st.session_state.auto_trade_min_conf}%")

if st.session_state.auto_refresh:
    time.sleep(st.session_state.refresh_rate)
    st.rerun()
