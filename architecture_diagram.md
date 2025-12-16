# SignalGen Architecture Diagram

## System Architecture Overview

```mermaid
graph TB
    subgraph "UI Layer"
        UI[PyWebView UI<br/>Tailwind + JS + WS]
    end
    
    subgraph "Application Layer"
        APP[App Controller<br/>FastAPI]
        WS[WebSocket Server]
        REST[REST API]
    end
    
    subgraph "Core Logic"
        RULE[Rule Engine<br/>Deterministic Evaluation]
        IND[Indicator Engine<br/>MA Calculations]
        STATE[State Machine<br/>WAIT→SIGNAL→COOLDOWN]
    end
    
    subgraph "Data Processing"
        SCALP[Scalping Engine<br/>ib_insync Integration]
        IBKR[IBKR TWS/Gateway<br/>Real-time Data]
    end
    
    subgraph "Storage & Broadcasting"
        DB[(SQLite Database)]
        BCAST[WebSocket Broadcaster]
    end
    
    UI -->|REST/WS| APP
    APP --> REST
    APP --> WS
    APP --> SCALP
    SCALP --> IBKR
    SCALP --> IND
    SCALP --> RULE
    SCALP --> STATE
    RULE --> BCAST
    SCALP --> DB
    BCAST --> UI
    
    style UI fill:#e1f5fe
    style APP fill:#f3e5f5
    style RULE fill:#e8f5e8
    style SCALP fill:#fff3e0
    style DB fill:#fce4ec
```

## Data Flow Diagram

```mermaid
sequenceDiagram
    participant UI as PyWebView UI
    participant APP as FastAPI App
    participant SCALP as Scalping Engine
    participant IBKR as IBKR Gateway
    participant RULE as Rule Engine
    participant WS as WebSocket
    participant DB as SQLite
    
    Note over UI,DB: Application Startup
    UI->>APP: Start Application
    APP->>DB: Initialize Database
    APP->>SCALP: Start Engine
    SCALP->>IBKR: Connect & Subscribe
    
    Note over UI,DB: Real-time Signal Generation
    IBKR->>SCALP: Real-time Bar Data
    SCALP->>RULE: Evaluate Rules
    RULE->>SCALP: Rule Result (True/False)
    SCALP->>DB: Store Signal
    SCALP->>WS: Broadcast Signal
    WS->>UI: Update UI
    
    Note over UI,DB: Rule Management
    UI->>APP: Create/Update Rule
    APP->>DB: Save Rule
    APP->>SCALP: Reload Rules
```

## Component Interaction Map

```mermaid
graph LR
    subgraph "Frontend"
        UI[PyWebView UI]
    end
    
    subgraph "Backend Services"
        API[REST API]
        WS_SVC[WebSocket Service]
    end
    
    subgraph "Business Logic"
        RE[Rule Engine]
        IE[Indicator Engine]
        SM[State Machine]
        SE[Scalping Engine]
    end
    
    subgraph "Data Layer"
        DB[(SQLite)]
        EXT[IBKR Gateway]
    end
    
    UI -.->|HTTP| API
    UI -.->|WebSocket| WS_SVC
    API --> DB
    WS_SVC --> SE
    SE --> RE
    SE --> IE
    SE --> SM
    SE --> DB
    SE --> EXT
    RE --> DB
```

## Directory Structure Visualization

```mermaid
graph TD
    ROOT[signalgen/]
    
    subgraph "app/"
        APP_DIR[app/]
        
        subgraph "ui/"
            UI_DIR[ui/]
            TEMPLATES[templates/]
            STATIC[static/]
        end
        
        subgraph "core/"
            CORE_DIR[core/]
            RULE_FILE[rule_engine.py]
            IND_FILE[indicator_engine.py]
            STATE_FILE[state_machine.py]
        end
        
        subgraph "engines/"
            ENG_DIR[engines/]
            SCALP_FILE[scalping_engine.py]
        end
        
        subgraph "storage/"
            STOR_DIR[storage/]
            DB_FILE[sqlite_repo.py]
        end
        
        subgraph "ws/"
            WS_DIR[ws/]
            BCAST_FILE[broadcaster.py]
        end
        
        APP_FILE[app.py]
        MAIN_FILE[main.py]
    end
    
    REQ_FILE[requirements.txt]
    README_FILE[README.md]
    GITIGNORE[.gitignore]
    MVP_FILE[PROJECT_MVP.md]
    
    ROOT --> APP_DIR
    ROOT --> REQ_FILE
    ROOT --> README_FILE
    ROOT --> GITIGNORE
    ROOT --> MVP_FILE
    
    APP_DIR --> UI_DIR
    APP_DIR --> CORE_DIR
    APP_DIR --> ENG_DIR
    APP_DIR --> STOR_DIR
    APP_DIR --> WS_DIR
    APP_DIR --> APP_FILE
    APP_DIR --> MAIN_FILE
    
    UI_DIR --> TEMPLATES
    UI_DIR --> STATIC
    
    CORE_DIR --> RULE_FILE
    CORE_DIR --> IND_FILE
    CORE_DIR --> STATE_FILE
    
    ENG_DIR --> SCALP_FILE
    
    STOR_DIR --> DB_FILE
    
    WS_DIR --> BCAST_FILE