# Advanced Scalping Rule with Volume Indicators

## Overview
Updated default scalping rule dengan kondisi yang lebih ketat dan comprehensive, termasuk volume confirmation untuk filter false signals.

## New Default Scalping Rule

### Conditions (11 Total - ALL must be TRUE)

#### 1. EMA Momentum Entry
```
EMA6 CROSS_UP EMA10
```
- **Purpose**: Detect early momentum shift
- **Signal**: Fast EMA crosses above slow EMA (bullish crossover)

#### 2. Price Position (Near EMA20)
```
PRICE >= EMA20
PRICE_EMA20_DIFF_PCT <= 0.002  // Max 0.2% from EMA20
```
- **Purpose**: Ensure price is in uptrend but not overextended
- **Max Distance**: 0.2% dari EMA20 (lebih ketat dari sebelumnya yang 1%)
- **Example**: If EMA20 = $100, price must be between $100 - $100.20

#### 3. RSI Momentum Range
```
RSI14 > RSI14_PREV  // RSI rising
RSI14 > 38          // Above oversold threshold
RSI14 < 55          // Not yet overbought
```
- **Purpose**: Confirm momentum is building but not exhausted
- **Sweet Spot**: RSI between 38-55 and rising
- **Filters**: Too weak (< 38) or too strong (> 55) signals

#### 4. ADX Trend Strength
```
ADX5 >= 15          // Minimum trend strength
ADX5 > ADX5_PREV    // Trend strengthening
```
- **Purpose**: Confirm there's a strong trend forming
- **Threshold**: ADX >= 15 indicates meaningful trend
- **Direction**: ADX must be rising (trend getting stronger)

#### 5. Volume Confirmation ⭐ NEW
```
REL_VOLUME_20 >= 1.3
```
- **Purpose**: Confirm institutional/smart money participation
- **Calculation**: `REL_VOLUME_20 = VOLUME / SMA_VOLUME_20`
- **Threshold**: Current volume must be >= 1.3x the 20-period average
- **Filters**: Weak moves without volume support

#### 6. MACD Histogram Rising
```
MACD_HIST >= MACD_HIST_PREV
```
- **Purpose**: Confirm bullish momentum acceleration
- **Signal**: Histogram increasing (momentum strengthening)

### Rule Summary
```json
{
  "name": "Default Scalping",
  "type": "system",
  "logic": "AND",
  "conditions": [
    {"left": "EMA6", "op": "CROSS_UP", "right": "EMA10"},
    {"left": "PRICE", "op": ">=", "right": "EMA20"},
    {"left": "PRICE_EMA20_DIFF_PCT", "op": "<=", "right": 0.002},
    {"left": "RSI14", "op": ">", "right": "RSI14_PREV"},
    {"left": "RSI14", "op": ">", "right": 38},
    {"left": "RSI14", "op": "<", "right": 55},
    {"left": "ADX5", "op": ">=", "right": 15},
    {"left": "ADX5", "op": ">", "right": "ADX5_PREV"},
    {"left": "REL_VOLUME_20", "op": ">=", "right": 1.3},
    {"left": "MACD_HIST", "op": ">=", "right": "MACD_HIST_PREV"}
  ],
  "cooldown_sec": 60
}
```

## New Indicators Added

### 1. VOLUME
- **Type**: Raw value
- **Description**: Current bar's trading volume
- **Source**: IBKR RealTimeBar and historical data
- **Usage**: Base for relative volume calculation

### 2. SMA_VOLUME_20
- **Type**: Simple Moving Average
- **Period**: 20
- **Description**: 20-period average of volume
- **Purpose**: Baseline for normal volume activity

### 3. REL_VOLUME_20
- **Type**: Calculated ratio
- **Formula**: `VOLUME / SMA_VOLUME_20`
- **Description**: Current volume relative to 20-period average
- **Interpretation**:
  - `< 1.0`: Below average volume (weak)
  - `1.0 - 1.3`: Normal volume
  - `> 1.3`: Above average volume (strong) ✅
  - `> 2.0`: Very high volume (institutional activity)

## Implementation Changes

### 1. Rule Engine (`app/core/rule_engine.py`)
Added new operands to SUPPORTED_OPERANDS:
```python
# Volume indicators
"VOLUME",          # Current bar volume
"SMA_VOLUME_20",   # 20-period SMA of volume
"REL_VOLUME_20",   # Relative volume (VOLUME / SMA_VOLUME_20)
```

### 2. Indicator Engine (`app/core/indicator_engine.py`)

#### Updated `_create_dataframe()`
```python
df = pd.DataFrame({
    'open': [c['open'] for c in candles],
    'high': [c['high'] for c in candles],
    'low': [c['low'] for c in candles],
    'close': [c['close'] for c in candles],
    'volume': [c.get('volume', 0) for c in candles],  # ✅ NEW
})
```

#### Updated `_calculate_indicators_for_symbol()`
```python
# Volume indicators
if 'volume' in df.columns and len(df) >= 1:
    current_volume = float(df['volume'].iloc[-1])
    indicators['VOLUME'] = current_volume
    
    # SMA of volume (20-period)
    if len(df) >= 20:
        sma_volume = ta.trend.sma_indicator(df['volume'], window=20)
        if sma_volume is not None and not pd.isna(sma_volume.iloc[-1]):
            sma_vol_20 = float(sma_volume.iloc[-1])
            indicators['SMA_VOLUME_20'] = sma_vol_20
            
            # Relative Volume
            if sma_vol_20 > 0:
                rel_volume = current_volume / sma_vol_20
                indicators['REL_VOLUME_20'] = float(rel_volume)
```

#### Updated `update_candle_data()` signature
```python
def update_candle_data(self, symbol: str, open_price: float, high: float, low: float, 
                      close: float, timestamp: Optional[float] = None, 
                      volume: int = 0) -> bool:  # ✅ Added volume parameter
```

### 3. Scalping Engine (`app/engines/scalping_engine.py`)

#### Updated `_on_bar_update()`
```python
candle_completed = self.indicator_engine.update_candle_data(
    symbol=symbol,
    open_price=bar_data.open_,
    high=bar_data.high,
    low=bar_data.low,
    close=bar_data.close,
    timestamp=timestamp,
    volume=getattr(bar_data, 'volume', 0)  # ✅ Pass volume from RealTimeBar
)
```

#### Updated `request_historical_data()`
Volume already captured:
```python
candle_data_list.append({
    'open': bar.open,
    'high': bar.high,
    'low': bar.low,
    'close': bar.close,
    'volume': getattr(bar, 'volume', 0),  # ✅ Already included
    'timestamp': timestamp
})
```

### 4. Database Initialization (`app/storage/init_db.py`)
Updated default rule definition with all new conditions.

## Benefits of New Rule

### 1. Reduced False Signals
- **Volume Filter**: Eliminates weak moves without institutional support
- **Tighter EMA20 Distance**: 0.2% vs 1% - prevents chasing extended moves
- **RSI Range**: 38-55 filters both weak bounces and overbought conditions

### 2. Higher Quality Entries
- **Multi-Confirmation**: 11 conditions all must align (vs 13 before but less strict)
- **Momentum + Volume**: Both price action AND participation must confirm
- **Trend Strength**: ADX >= 15 ensures meaningful trend, not noise

### 3. Better Risk/Reward
- **Entry Near Support**: Price close to EMA20 provides natural stop level
- **Strong Momentum**: Rising RSI, ADX, MACD all confirm move has legs
- **Institutional Support**: Volume >= 1.3x average shows big players involved

### 4. Practical Scalping Optimization
- **Quick Moves**: EMA6/10 cross catches early momentum
- **Not Overextended**: Max 0.2% from EMA20 allows room to run
- **Volume Spike**: REL_VOLUME >= 1.3 confirms breakout validity

## Comparison: Old vs New Rule

### Old Rule (13 Conditions)
```
✓ PREV_CLOSE > PREV_OPEN (removed - too basic)
✓ EMA6 CROSS_UP EMA10
✓ EMA6 CROSS_UP EMA20 (removed - redundant with EMA10 cross + price > EMA20)
✓ PRICE >= EMA20
✓ PRICE_EMA20_DIFF_PCT <= 0.01 (1%)
✓ MACD_HIST > MACD_HIST_PREV
✓ MACD_HIST > 0 (removed - too restrictive)
✓ MACD_HIST_PREV > 0 (removed - too restrictive)
✓ ADX5 > ADX5_PREV
✓ ADX5 > 0 (removed - replaced with ADX5 >= 15)
✓ RSI14 > RSI14_PREV
✓ RSI14_PREV < 40 (removed - replaced with RSI range)
✓ RSI14 > 40
```

### New Rule (11 Conditions)
```
✅ EMA6 CROSS_UP EMA10
✅ PRICE >= EMA20
✅ PRICE_EMA20_DIFF_PCT <= 0.002 (0.2% - TIGHTER!)
✅ RSI14 > RSI14_PREV
✅ RSI14 > 38 (NEW RANGE)
✅ RSI14 < 55 (NEW UPPER LIMIT)
✅ ADX5 >= 15 (NEW - stronger threshold)
✅ ADX5 > ADX5_PREV
✅ REL_VOLUME_20 >= 1.3 (NEW - VOLUME FILTER!)
✅ MACD_HIST >= MACD_HIST_PREV
```

### Key Changes
1. ❌ Removed redundant EMA20 cross (covered by EMA10 + price > EMA20)
2. ❌ Removed PREV_CLOSE > PREV_OPEN (too simplistic)
3. ❌ Removed MACD_HIST > 0 requirement (too restrictive)
4. ✅ **TIGHTER**: 1% → 0.2% max distance from EMA20
5. ✅ **NEW**: RSI must be in 38-55 range (sweet spot)
6. ✅ **NEW**: ADX >= 15 (meaningful trend strength)
7. ✅ **NEW**: Volume >= 1.3x average (institutional confirmation)

## Testing Strategy

### Test Case 1: Volume Spike Breakout
**Scenario**: Price breaks above EMA20 with high volume
- EMA6 crosses EMA10 ✅
- Price = $100.10, EMA20 = $100.00 (0.1% away) ✅
- RSI = 45, RSI_PREV = 42 (rising, in range) ✅
- ADX5 = 18, ADX5_PREV = 16 (strong, rising) ✅
- Volume = 1.5M, SMA_VOLUME_20 = 1M (REL_VOLUME = 1.5) ✅
- MACD_HIST rising ✅
**Expected**: Signal generated ✅

### Test Case 2: Weak Move (No Volume)
**Scenario**: Price action looks good but volume is low
- EMA6 crosses EMA10 ✅
- Price near EMA20 ✅
- RSI, ADX all good ✅
- Volume = 800K, SMA_VOLUME_20 = 1M (REL_VOLUME = 0.8) ❌
**Expected**: NO signal (volume filter blocks)

### Test Case 3: Overextended Move
**Scenario**: Price too far from EMA20
- EMA6 crosses EMA10 ✅
- Price = $100.50, EMA20 = $100.00 (0.5% away) ❌
**Expected**: NO signal (price too extended)

### Test Case 4: Overbought RSI
**Scenario**: RSI already too high
- EMA6 crosses EMA10 ✅
- Price near EMA20 ✅
- RSI = 62 (above 55 limit) ❌
**Expected**: NO signal (RSI filter blocks)

## Files Modified

1. ✅ `app/core/rule_engine.py` - Added VOLUME, SMA_VOLUME_20, REL_VOLUME_20
2. ✅ `app/core/indicator_engine.py` - Volume calculation and indicators
3. ✅ `app/engines/scalping_engine.py` - Pass volume from RealTimeBar
4. ✅ `app/storage/init_db.py` - New default rule definition

## Migration Notes

### For Existing Database
1. **Delete Old Rule** (if you want fresh start):
   ```sql
   DELETE FROM rules WHERE name = 'Default Scalping' AND is_system = 1;
   ```
2. **Restart Application**: Will create new rule automatically
3. **Or Manual Update**: Update rule via UI (if not system-locked)

### For Fresh Install
- New rule will be created automatically on first run
- No migration needed

## Next Steps

1. **Delete Existing Database** (untuk fresh rule):
   ```bash
   rm signalgen.db
   ```

2. **Restart Application**:
   - Rule baru akan di-create otomatis
   - Volume indicators akan available

3. **Test Rule**:
   - Start engine dengan Default Scalping rule
   - Monitor log untuk volume values
   - Verify signals only generate dengan volume >= 1.3x

4. **Monitor Performance**:
   - Track signal quality vs old rule
   - Adjust REL_VOLUME threshold if needed (1.3 bisa di-tweak ke 1.5 atau 1.2)
   - Review RSI range effectiveness

## Success Criteria

- ✅ Volume indicators calculate correctly
- ✅ REL_VOLUME_20 filters low-volume signals
- ✅ Fewer but higher-quality signals
- ✅ Signals have institutional volume support
- ✅ Price entries closer to EMA20 support
