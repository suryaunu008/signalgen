# SignalGen - Real-time Scalping Signal Generator

SignalGen is a desktop application for real-time scalping signal generation with customizable rules, real-time data from IBKR, and WebSocket output for external execution systems.

## Features

- **Real-time Signal Generation**: Generate trading signals based on customizable rules
- **IBKR Integration**: Connect to Interactive Brokers TWS/Gateway for live market data
- **Customizable Rules**: Create and manage trading rules with logical conditions
- **WebSocket Broadcasting**: Real-time signal distribution to UI and external systems
- **Desktop UI**: Native desktop application using PyWebView
- **Local Storage**: SQLite database for rules, watchlists, and signal history
- **Technical Analysis**: Built-in indicators using pandas, numpy, and TA-Lib

## Architecture

```
┌──────────────────────────────┐
│        PyWebView UI          │
│   (Tailwind + JS + WS)       │
└───────────────┬──────────────┘
                │ REST / WS
                ▼
┌──────────────────────────────┐
│       App Controller         │
│     (FastAPI)              │
│  - REST API                  │
│  - WebSocket Server          │
│  - Engine Orchestrator       │
└───────────────┬──────────────┘
                │
        ┌───────┴────────┐
        │                │
        ▼                ▼
┌──────────────┐  ┌─────────────────┐
│ Rule Engine  │  │ Scalping Engine │
│ (determin.) │  │  (ib_insync)    │
└───────┬──────┘  └───────┬─────────┘
        │                │
        └───────┬────────┘
                ▼
          SQLite Storage
```

## Quick Start

### Prerequisites

- Python 3.8 or higher
- Interactive Brokers TWS or Gateway
- IBKR market data subscriptions

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd signalgen
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**
   ```bash
   python -m app.main
   ```

### First Time Setup

1. Launch Interactive Brokers TWS or Gateway
2. Configure API connections in IBKR (enable API connections)
3. Start SignalGen - it will automatically:
   - Create the SQLite database
   - Seed default rules and watchlist
   - Start the web interface

## Usage

### Creating Rules

Rules are defined using logical conditions with technical indicators:

**Example Rule**: "PRICE > MA5 AND MA5 > MA10"

**Supported Operands**:
- `PRICE` - Current price
- `MA5` - 5-period moving average
- `MA10` - 10-period moving average
- `MA20` - 20-period moving average

**Supported Operators**:
- `>` - Greater than
- `<` - Less than
- `>=` - Greater than or equal
- `<=` - Less than or equal

### Managing Watchlists

- Maximum 5 symbols per watchlist (MVP limitation)
- One active watchlist at a time
- Cannot modify watchlist while engine is running

### Engine Control

1. **Start Engine**: Select watchlist and rule, then start
2. **Monitor**: View real-time signals in the UI
3. **Stop Engine**: Stop signal generation when needed

## API Documentation

Once running, the API is available at `http://localhost:3456/docs`

### Key Endpoints

- `GET /api/rules` - List all rules
- `POST /api/rules` - Create new rule
- `GET /api/watchlists` - List all watchlists
- `POST /api/watchlists` - Create new watchlist
- `POST /api/engine/start` - Start scalping engine
- `POST /api/engine/stop` - Stop scalping engine
- `GET /api/signals` - Get signal history

## WebSocket Events

Connect to `ws://localhost:8765` for real-time events:

- `signal` - New trading signal generated
- `engine_status` - Engine state changes
- `watchlist_update` - Watchlist modifications
- `rule_update` - Rule modifications

## Configuration

Default settings are automatically created on first run:

```json
{
  "ib_host": "127.0.0.1",
  "ib_port": 7497,
  "ib_client_id": 1,
  "max_watchlist_symbols": 5,
  "default_cooldown": 60,
  "bar_size": 5,
  "ui_theme": "light"
}
```

## Dependencies

### Core Dependencies

- **fastapi==0.104.1** - Web framework for REST API
- **uvicorn[standard]==0.24.0** - ASGI server
- **pywebview==4.4.1** - Desktop UI wrapper
- **ib_insync==0.9.86** - IBKR API integration

### WebSocket & Real-time

- **python-socketio==5.10.0** - Socket.IO server
- **python-engineio==4.7.1** - Socket.IO engine

### Technical Analysis

- **pandas==2.1.4** - Data manipulation
- **numpy==1.25.2** - Numerical operations
- **ta-lib==0.4.28** - Technical analysis functions
- **talib-binary==0.4.24** - TA-Lib binary distribution

### Utilities

- **python-multipart==0.0.6** - Form data handling
- **jinja2==3.1.2** - Template engine
- **pydantic==2.5.0** - Data validation

## Project Structure

```
signalgen/
├── app/
│   ├── ui/
│   │   ├── templates/          # HTML templates
│   │   └── static/             # CSS, JS, images
│   ├── core/
│   │   ├── rule_engine.py      # Rule evaluation logic
│   │   ├── indicator_engine.py # Technical indicators
│   │   └── state_machine.py    # Engine state management
│   ├── engines/
│   │   └── scalping_engine.py  # Main scalping engine
│   ├── storage/
│   │   └── sqlite_repo.py      # Database operations
│   ├── ws/
│   │   └── broadcaster.py      # WebSocket broadcasting
│   ├── app.py                  # FastAPI application
│   └── main.py                 # Application entry point
├── requirements.txt               # Python dependencies
├── README.md                   # This file
├── .gitignore                  # Git ignore file
└── PROJECT_MVP.md             # Project specification
```

## MVP Limitations

The current MVP version has these intentional limitations:

- ❌ Multi-rule active execution
- ❌ Multi-timeframe support
- ❌ Auto execution
- ❌ Complex risk management
- ❌ Backtesting capabilities
- ❌ Maximum 5 symbols per watchlist
- ❌ One active watchlist at a time

These limitations are designed to keep the MVP focused and achievable within a one-week development timeframe.

## Development

### Running in Development Mode

```bash
# Install development dependencies
pip install -r requirements.txt

# Run the application
python -m app.main
```

### Database Schema

The application uses SQLite with these tables:

- `rules` - Trading rules with JSON definitions
- `watchlists` - Symbol watchlists
- `watchlist_items` - Individual symbols in watchlists
- `signals` - Generated trading signals
- `settings` - Application configuration

## Troubleshooting

### Common Issues

1. **IBKR Connection Failed**
   - Ensure TWS/Gateway is running
   - Check API connections are enabled in IBKR
   - Verify port (7497 for TWS, 4002 for Gateway)

2. **No Market Data**
   - Verify market data subscriptions in IBKR
   - Check symbol validity (e.g., AAPL, MSFT, GOOGL)

3. **Application Won't Start**
   - Check Python version (3.8+ required)
   - Verify all dependencies installed
   - Check log file for errors

### Logs

Application logs are saved to `signalgen.log` in the application directory.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
- Check the troubleshooting section
- Review the API documentation at `/docs`
- Check the application logs
- Create an issue in the repository

---

**SignalGen** - Real-time scalping signal generation for modern traders.