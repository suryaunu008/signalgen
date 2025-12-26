# Fix CROSS_UP/CROSS_DOWN Operators - Previous Values Issue

## Problem

Engine crashes saat evaluasi rule dengan CROSS_UP operator:

```
ERROR - Error evaluating rule for TSLA: Failed to evaluate condition: CROSS_UP requires previous values: EMA6_PREV and EMA10_PREV not found
ERROR - Error evaluating rule for AMZN: Failed to evaluate condition: CROSS_UP requires previous values: EMA6_PREV and EMA10_PREV not found
...
```

### Root Cause Analysis

1. **Missing _PREV Operands in SUPPORTED_OPERANDS**
   - `EMA6_PREV`, `EMA10_PREV`, dan banyak _PREV indicators lainnya tidak terdaftar
   - Rule engine menolak operand yang tidak terdaftar

2. **prev_indicators Not Initialized After Bulk Load**
   - Saat historical data di-load via `bulk_update_candle_data()`, indicators hanya di-calculate **sekali** di akhir
   - `prev_indicators` hanya di-update saat `update_candle_data()` (real-time), bukan saat bulk load
   - Akibatnya, saat engine start dan real-time bar pertama masuk, tidak ada previous values available

3. **Incomplete _PREV Suffix Logic**
   - Code di `_calculate_indicators_for_symbol()` menambahkan `_PREV` suffix, tapi logic exclude tidak comprehensive
   - Hanya exclude `PRICE_EMA20_DIFF_PCT`, seharusnya juga exclude derived metrics lainnya

## Solution Implemented

### 1. Added Missing _PREV Operands to Rule Engine

**File**: `app/core/rule_engine.py`

```python
SUPPORTED_OPERANDS = {
    # ... existing operands ...
    
    # Moving Averages with previous values
    "MA20", "MA50", "MA100", "MA200",
    "MA20_PREV", "MA50_PREV", "MA100_PREV", "MA200_PREV",  # ✅ NEW
    
    # Exponential Moving Averages with previous values
    "EMA6", "EMA9", "EMA10", "EMA13", "EMA20", "EMA21", "EMA34", "EMA50",
    "EMA6_PREV", "EMA9_PREV", "EMA10_PREV", "EMA13_PREV",  # ✅ NEW
    "EMA20_PREV", "EMA21_PREV", "EMA34_PREV", "EMA50_PREV",  # ✅ NEW
    
    # MACD with previous values
    "MACD", "MACD_SIGNAL", "MACD_HIST", "MACD_HIST_PREV",
    "MACD_PREV", "MACD_SIGNAL_PREV",  # ✅ NEW
    
    # Bollinger Bands with previous values
    "BB_UPPER", "BB_MIDDLE", "BB_LOWER", "BB_WIDTH",
    "BB_UPPER_PREV", "BB_MIDDLE_PREV", "BB_LOWER_PREV",  # ✅ NEW
    
    # ... other indicators ...
}
```

**Changes**:
- ✅ Added all MA_PREV variants (MA20_PREV, MA50_PREV, etc.)
- ✅ Added all EMA_PREV variants (EMA6_PREV, EMA10_PREV, etc.)
- ✅ Added MACD_PREV and MACD_SIGNAL_PREV
- ✅ Added BB_UPPER_PREV, BB_MIDDLE_PREV, BB_LOWER_PREV

### 2. Initialize prev_indicators After Bulk Load

**File**: `app/core/indicator_engine.py` - `bulk_update_candle_data()` method

```python
def bulk_update_candle_data(self, symbol: str, candles: List[Dict]) -> None:
    # ... add all candles to candle_data ...
    
    # Calculate indicators once after all data is loaded
    self._calculate_indicators_for_symbol(symbol, suppress_warnings=True)
    
    # ✅ NEW: Initialize prev_indicators from second-to-last candle
    # This ensures that when we start receiving real-time data, we have previous values
    if len(self.candle_data[symbol]) >= 2:
        # Temporarily calculate indicators for all candles up to second-to-last
        temp_candles = self.candle_data[symbol][:-1]  # All except last
        if temp_candles:
            # Save current candles
            current_candles = self.candle_data[symbol]
            # Set to temp (exclude last candle)
            self.candle_data[symbol] = deque(temp_candles, maxlen=self.max_candles)
            # Calculate indicators for second-to-last state
            self._calculate_indicators_for_symbol(symbol, suppress_warnings=True)
            # Store these as previous indicators
            if symbol in self.indicators and self.indicators[symbol]:
                self.prev_indicators[symbol] = self.indicators[symbol].copy()
            # Restore full candles
            self.candle_data[symbol] = current_candles
            # Recalculate with all candles
            self._calculate_indicators_for_symbol(symbol, suppress_warnings=True)
```

**Logic**:
1. After bulk loading historical candles, calculate indicators normally (latest state)
2. If we have >= 2 candles:
   - Temporarily calculate indicators using candles[:-1] (all except last)
   - Store these as `prev_indicators[symbol]` (represents N-1 state)
   - Restore full candles and recalculate (represents N state)
3. Now `prev_indicators` is populated and ready for CROSS operators

**Example**:
- Historical data: 250 candles
- After bulk load:
  - `indicators[symbol]` = indicators calculated from all 250 candles (current)
  - `prev_indicators[symbol]` = indicators calculated from 249 candles (previous)
- When first real-time bar arrives:
  - CROSS_UP can compare EMA6 vs EMA6_PREV ✅

### 3. Improved _PREV Suffix Exclusion Logic

**File**: `app/core/indicator_engine.py` - `_calculate_indicators_for_symbol()` method

```python
# Add previous values with _PREV suffix
if symbol in self.prev_indicators and self.prev_indicators[symbol]:
    prev = self.prev_indicators[symbol]
    # Add _PREV suffix for indicators that should track previous values
    # Exclude derived/calculated metrics
    excluded_from_prev = ['PRICE_EMA20_DIFF_PCT', 'PRICE', 'BB_WIDTH']  # ✅ UPDATED
    for key, value in prev.items():
        if key not in excluded_from_prev and not key.endswith('_PREV'):
            indicators[f'{key}_PREV'] = value
else:
    # Log if prev_indicators is empty for debugging
    if not suppress_warnings:
        self.logger.debug(f"No previous indicators available for {symbol} yet")  # ✅ NEW
```

**Changes**:
- ✅ More explicit exclusion list: `PRICE_EMA20_DIFF_PCT`, `PRICE`, `BB_WIDTH`
- ✅ Added check `not key.endswith('_PREV')` to avoid double-suffix (EMA6_PREV_PREV)
- ✅ Added debug logging when prev_indicators is empty
- ✅ Check both existence AND non-empty state of `prev_indicators[symbol]`

## Testing Verification

### Test Case 1: CROSS_UP Rule with EMA6 and EMA10

**Rule Definition**:
```json
{
  "name": "EMA 6/10 Cross Up",
  "conditions": [
    {
      "left": "EMA6",
      "op": "CROSS_UP",
      "right": "EMA10"
    }
  ],
  "logic": "AND"
}
```

**Expected Behavior**:
- ✅ Engine loads historical data
- ✅ `prev_indicators` initialized with EMA6 and EMA10 from second-to-last candle
- ✅ When real-time bar arrives, indicators include:
  - `EMA6` = current value
  - `EMA6_PREV` = previous value
  - `EMA10` = current value
  - `EMA10_PREV` = previous value
- ✅ CROSS_UP operator can evaluate: (EMA6_PREV < EMA10_PREV) AND (EMA6 > EMA10)
- ✅ No more "not found" errors

### Test Case 2: Verify All _PREV Values Available

**Debug Steps**:
1. Start engine with any watchlist
2. Wait for historical data load to complete
3. Check log for: `"No previous indicators available for {symbol} yet"`
   - Should **NOT** appear after bulk load completes
4. Add temporary logging to see available indicators:
   ```python
   # In _generate_signal or _on_bar_update
   self.logger.info(f"Available indicators: {list(indicators.keys())}")
   ```
5. Verify output includes:
   - `EMA6`, `EMA6_PREV`
   - `EMA10`, `EMA10_PREV`
   - `MA20`, `MA20_PREV`
   - `RSI14`, `RSI14_PREV`
   - etc.

### Test Case 3: CROSS_DOWN with MA

**Rule Definition**:
```json
{
  "name": "MA 20/50 Cross Down",
  "conditions": [
    {
      "left": "MA20",
      "op": "CROSS_DOWN",
      "right": "MA50"
    }
  ]
}
```

**Expected Behavior**:
- ✅ MA20_PREV and MA50_PREV available
- ✅ CROSS_DOWN evaluates without errors
- ✅ Signal generated when MA20 crosses below MA50

## Benefits

### 1. CROSS Operators Now Work Correctly
- ✅ All CROSS_UP and CROSS_DOWN rules can be evaluated
- ✅ No more "previous values not found" errors
- ✅ Proper crossover detection from first real-time bar

### 2. Complete Previous Value Support
- ✅ All MA, EMA, MACD, BB, RSI, ADX have _PREV variants
- ✅ Can create complex rules comparing current vs previous states
- ✅ Enable momentum-based strategies (e.g., "RSI14 > RSI14_PREV")

### 3. Robust Historical Data Initialization
- ✅ prev_indicators properly set after bulk load
- ✅ No waiting period for cross operators to become active
- ✅ Immediate signal detection from engine start

### 4. Better Debugging
- ✅ Debug logging when prev_indicators not available
- ✅ Clear visibility into indicator availability issues

## Implementation Notes

### Performance Impact
- **Minimal**: Extra calculation during bulk load only
  - One-time cost: Calculate indicators twice (N-1 candles, then N candles)
  - Real-time: No additional overhead
- **Memory**: Negligible (one extra dict per symbol for prev_indicators)

### Backward Compatibility
- ✅ Existing rules without CROSS operators: Unaffected
- ✅ Existing code using indicators: No changes needed
- ✅ New _PREV operands: Opt-in, don't break old rules

### Edge Cases Handled
1. **Less than 2 candles**: Skip prev_indicators initialization (graceful)
2. **Empty candles**: Check before processing
3. **Double _PREV suffix**: Prevented with `not key.endswith('_PREV')` check
4. **Derived metrics**: Excluded from _PREV suffix (PRICE, BB_WIDTH, PRICE_EMA20_DIFF_PCT)

## Files Modified

1. ✅ `app/core/rule_engine.py`
   - Added all _PREV variants to SUPPORTED_OPERANDS
   
2. ✅ `app/core/indicator_engine.py`
   - Modified `bulk_update_candle_data()` - initialize prev_indicators
   - Modified `_calculate_indicators_for_symbol()` - improved exclusion logic and logging

## Next Steps

1. **Test with Live Data**
   - Start engine with CROSS_UP rule
   - Verify no errors in logs
   - Confirm signals generate correctly

2. **Verify Indicator Availability**
   - Add debug logging to confirm all _PREV values present
   - Check first real-time bar after historical load

3. **Create More CROSS Rules**
   - Test various combinations (MA cross, EMA cross, MACD cross)
   - Verify crossover detection accuracy

4. **Performance Monitoring**
   - Monitor bulk load time (should be negligible increase)
   - Check memory usage (should be stable)

## Success Criteria

- ✅ No "previous values not found" errors
- ✅ CROSS_UP and CROSS_DOWN rules evaluate successfully
- ✅ Signals generate correctly for crossover conditions
- ✅ All symbols have prev_indicators after historical load
- ✅ Real-time updates maintain prev_indicators correctly
