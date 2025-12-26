# Signal Generation Debug Enhancement

## Overview
Enhanced signal generation logging dan storage untuk debugging akurasi signal dengan menambahkan indicator values pada saat signal di-generate.

## Problem Statement
User melaporkan discrepancy antara expected signal generation dengan actual:
- **Rule**: `PRICE < BB_MIDDLE`
- **Expected**: Signal tidak seharusnya generated saat price 314.12 (karena BB_MIDDLE = 314.00)
- **Actual**: Signal ter-generate di price 314.12
- **Root Cause**: Tidak ada logging indicator values saat signal generation, sulit untuk debug

## Solution Implemented

### 1. Enhanced Signal Generation Logging (`scalping_engine.py`)

#### Modified `_generate_signal()` Method
```python
def _generate_signal(self, symbol: str, price: float, timestamp: float, indicators: Dict[str, float]) -> None:
    """Generate signal with full indicator values logging"""
    
    # Include all indicator values in signal data
    signal_data = {
        'symbol': symbol,
        'price': price,
        'rule_id': self.active_rule['id'],
        'timestamp': datetime.fromtimestamp(timestamp).isoformat(),
        'indicators': indicators.copy()  # Store all indicators
    }
    
    # Log signal header
    rule_name = self.active_rule.get('name', 'Unknown')
    self.logger.info(
        f"🎯 SIGNAL GENERATED | Symbol: {symbol} | Price: {price:.2f} | Rule: {rule_name}"
    )
    
    # Log all relevant indicator values from rule conditions
    conditions = self.active_rule.get('definition', {}).get('conditions', [])
    if not conditions:
        conditions = self.active_rule.get('conditions', [])
    
    self.logger.info(f"📊 Indicator Values at Signal:")
    for condition in conditions:
        left = condition.get('left', '')
        right = condition.get('right', '')
        op = condition.get('op', '')
        
        # Log left operand value
        if left in indicators:
            self.logger.info(f"   {left} = {indicators[left]:.4f}")
        
        # Log right operand value if it's an indicator
        if isinstance(right, str) and right in indicators:
            self.logger.info(f"   {right} = {indicators[right]:.4f}")
        
        # Log the condition evaluation
        left_val = indicators.get(left, left)
        right_val = indicators.get(right, right) if isinstance(right, str) else right
        self.logger.info(f"   Condition: {left} ({left_val:.4f}) {op} {right} ({right_val:.4f})")
    
    # Also log PRICE for reference
    if 'PRICE' in indicators:
        self.logger.info(f"   PRICE = {indicators['PRICE']:.4f}")
```

**Key Features**:
- ✅ Logs signal header dengan emoji untuk visibility
- ✅ Extracts dan logs semua indicator values yang digunakan dalam rule conditions
- ✅ Logs nilai left operand, right operand, dan hasil evaluasi kondisi
- ✅ Includes PRICE untuk reference
- ✅ Stores indicator values dalam signal_data untuk database

#### Modified `_on_bar_update()` Call
```python
if rule_result:
    # Generate signal with indicator values for debugging
    self._generate_signal(symbol, bar_data.close, timestamp, indicators)
```

**Changes**:
- Added `indicators` parameter to `_generate_signal()` call
- Passes current indicator values at time of signal generation

### 2. Enhanced Rule Evaluation Logging (`rule_engine.py`)

#### Modified `evaluate_condition()` Method
```python
def evaluate_condition(self, condition: Dict[str, Any], indicator_values: Dict[str, float]) -> bool:
    # ... existing code ...
    
    # Get values for operands
    left_value = self._get_operand_value(left_operand, indicator_values)
    right_value = self._get_operand_value(right_operand, indicator_values)
    
    # Log condition evaluation for debugging
    result = self.operators.get(operator)(left_value, right_value)
    logger.debug(
        f"Condition: {left_operand}({left_value:.4f}) {operator} {right_operand}({right_value:.4f}) = {result}"
    )
    
    return result
```

**Key Features**:
- ✅ Logs setiap condition evaluation dengan actual values
- ✅ Shows comparison result (True/False)
- ✅ Uses DEBUG level untuk detail tracking

### 3. Database Enhancement (`sqlite_repo.py`)

#### Added `indicators` Column to Signals Table
```python
# Create signals table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        time TEXT NOT NULL,
        symbol TEXT NOT NULL,
        price REAL NOT NULL,
        rule_id INTEGER,
        indicators TEXT,  -- NEW: JSON string of indicator values
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (rule_id) REFERENCES rules(id) ON DELETE SET NULL
    )
''')

# Check if indicators column exists, add it if not (migration)
cursor.execute("PRAGMA table_info(signals)")
columns = [column[1] for column in cursor.fetchall()]
if 'indicators' not in columns:
    cursor.execute('ALTER TABLE signals ADD COLUMN indicators TEXT')
    self.logger.info("Added indicators column to signals table")
```

**Migration Support**:
- ✅ Auto-detects existing databases
- ✅ Adds `indicators` column if missing
- ✅ No data loss for existing signals
- ✅ Backward compatible

#### Modified `save_signal()` Method
```python
def save_signal(self, signal_data: Dict) -> int:
    # Convert indicators dict to JSON string if present
    indicators_json = None
    if 'indicators' in signal_data and signal_data['indicators']:
        indicators_json = json.dumps(signal_data['indicators'])
    
    cursor.execute('''
        INSERT INTO signals (time, symbol, price, rule_id, indicators)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        signal_data['timestamp'],
        signal_data['symbol'],
        signal_data['price'],
        signal_data.get('rule_id'),
        indicators_json  -- Store indicators as JSON
    ))
```

**Key Features**:
- ✅ Serializes indicator dict to JSON
- ✅ Handles None/missing indicators gracefully
- ✅ Preserves all indicator values at signal time

#### Modified `get_signals()` Method
```python
def get_signals(self, limit: int = 100, symbol: str = None) -> List[Dict]:
    # ... query execution ...
    
    signals = []
    for row in rows:
        signal = dict(row)
        # Parse indicators JSON if present
        if signal.get('indicators'):
            try:
                signal['indicators'] = json.loads(signal['indicators'])
            except json.JSONDecodeError:
                signal['indicators'] = None
        signals.append(signal)
    return signals
```

**Key Features**:
- ✅ Auto-parses JSON indicators back to dict
- ✅ Error handling untuk corrupted JSON
- ✅ Returns indicators dalam format yang mudah digunakan

## Expected Log Output

### Example: Signal Generation for PRICE < BB_MIDDLE

```
INFO: 🎯 SIGNAL GENERATED | Symbol: GOOGL | Price: 314.12 | Rule: Test BB Middle
INFO: 📊 Indicator Values at Signal:
INFO:    PRICE = 314.1200
INFO:    BB_MIDDLE = 314.1500
INFO:    Condition: PRICE (314.1200) < BB_MIDDLE (314.1500)
DEBUG: Condition: PRICE(314.1200) < BB_MIDDLE(314.1500) = True
```

**Analysis dari log output**:
- Jika BB_MIDDLE = 314.15, maka signal BENAR (314.12 < 314.15) ✅
- Jika BB_MIDDLE = 314.00, maka signal SALAH (314.12 > 314.00) ❌
- Log ini akan reveal nilai BB_MIDDLE sebenarnya yang di-calculate

## Debugging Workflow

### Step 1: Start Engine dengan Rule
```bash
# Pilih watchlist dengan GOOGL
# Pilih rule: PRICE < BB_MIDDLE
# Start engine
```

### Step 2: Tunggu Signal Generation
Monitor log file untuk melihat output seperti di atas.

### Step 3: Compare dengan TradingView
- Open GOOGL di TradingView
- Set timeframe yang sama (e.g., 1m, 5m)
- Compare BB_MIDDLE value di TradingView vs logged value
- Compare signal price dengan current price di TradingView

### Step 4: Identify Discrepancy
Possible causes jika ada discrepancy:
1. **Timeframe mismatch**: TradingView menggunakan timeframe berbeda
2. **BB period mismatch**: Default period berbeda (20 vs lainnya)
3. **Data source delay**: IBKR data vs TradingView data feed
4. **Calculation method**: pandas-ta vs TradingView implementation
5. **Candle aggregation issue**: 5-second bars aggregation tidak sesuai

### Step 5: Verify in Database
```python
# Query signal dengan indicator values
signals = repo.get_signals(limit=10)
for signal in signals:
    print(f"Signal: {signal['symbol']} @ {signal['price']}")
    if signal.get('indicators'):
        print(f"  BB_MIDDLE: {signal['indicators'].get('BB_MIDDLE')}")
        print(f"  PRICE: {signal['indicators'].get('PRICE')}")
```

## Benefits

### 1. Full Signal Transparency
- ✅ Every signal includes all indicator values at generation time
- ✅ Can replay/verify signals against historical data
- ✅ Complete audit trail for backtesting

### 2. Easy Debugging
- ✅ Immediately see which indicators triggered signal
- ✅ Compare calculated vs expected values
- ✅ Identify calculation errors or configuration issues

### 3. Database Enrichment
- ✅ Signals stored dengan full context
- ✅ Can query signals by indicator ranges
- ✅ Historical analysis possible

### 4. Future Enhancement Ready
- ✅ Can add signal scoring based on indicator strength
- ✅ Can filter signals by indicator thresholds
- ✅ Can implement machine learning features

## Testing Checklist

- [ ] Start engine dengan existing database (test migration)
- [ ] Generate signal dan verify log output shows indicators
- [ ] Check database untuk indicators column
- [ ] Query signal dari API dan verify indicators included
- [ ] Compare indicator values dengan TradingView
- [ ] Test dengan multiple rules (AND conditions)
- [ ] Test dengan CROSS_UP/CROSS_DOWN operators
- [ ] Verify signal cooldown masih works
- [ ] Test dengan semua 5 symbols

## Files Modified

1. ✅ `app/engines/scalping_engine.py`
   - Modified `_generate_signal()` - added indicators parameter dan logging
   - Modified `_on_bar_update()` - pass indicators to _generate_signal

2. ✅ `app/core/rule_engine.py`
   - Modified `evaluate_condition()` - added debug logging

3. ✅ `app/storage/sqlite_repo.py`
   - Modified `initialize_database()` - added indicators column with migration
   - Modified `save_signal()` - serialize indicators to JSON
   - Modified `get_signals()` - deserialize indicators from JSON

## Next Steps

1. **Test Live**: Jalankan engine dan lihat log output actual
2. **Verify Calculation**: Compare dengan TradingView untuk GOOGL
3. **Identify Root Cause**: Jika ada discrepancy, cek:
   - Bollinger Bands period configuration
   - Timeframe matching
   - Candle aggregation accuracy
4. **Fix if Needed**: Update BB calculation atau candle builder sesuai findings

## Technical Notes

### Indicator Storage Format
```json
{
  "PRICE": 314.12,
  "BB_UPPER": 316.45,
  "BB_MIDDLE": 314.15,
  "BB_LOWER": 311.85,
  "BB_WIDTH": 4.60,
  "RSI14": 56.78,
  "MA20": 313.50,
  "EMA20": 314.00,
  // ... all other indicators
}
```

### Performance Impact
- **Minimal**: JSON serialization is fast
- **Storage**: ~500-1000 bytes per signal (acceptable)
- **Query**: Indexed by time/symbol, indicators don't affect performance
- **Logging**: INFO level, can be disabled in production if needed

### Backward Compatibility
- ✅ Existing signals without indicators: `indicators = NULL`
- ✅ New signals: `indicators = JSON string`
- ✅ API returns both old and new format
- ✅ No breaking changes
