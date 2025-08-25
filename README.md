# Asian Liquidity Sweep Trading Dashboard - User Manual

## Quick Start Guide

### 1. Connect to MT5
1. Enter your MT5 account credentials:
   - Account Number: Your MT5 account number
   - Password: Your MT5 password
   - Server: MetaQuotes-Demo (for demo accounts)
2. Click "Connect button
3. Wait for connection confirmation

### 2. Initialize Trading Session
1. Click "Initialize Session" button
2. System will create or load existing session
3. Asian range data will be displayed

### 3. Start Auto Mode
1. Click "Run Strategy (Auto)" button
2. System starts monitoring market every 2 seconds
3. "Stop Auto Mode" button appears
4. Monitor progress in System Status and logs

## Dashboard Components

### Connection Status
- Red Dot: Disconnected
- Green Dot: Connected to MT5
- Shows current connection state

### Trading Analysis Panel
- Asian Range Data: High, Low, Midpoint, Range size, Grade
- Manual Control Buttons: Initialize, Detect Sweep, Confirm Reversal, Generate Signal
- Run Full Analysis: State-aware analysis workflow

### State Machine
Visual representation of current trading state:
- IDLE: Ready for sweep detection
- SWEPT: Sweep detected, waiting for reversal
- CONFIRMED: Reversal confirmed, ready for signal
- ARMED: Signal generated, ready for execution
- IN_TRADE: Position open, monitoring

### System Status
Real-time status updates showing:
- What the system is currently doing
- What it's waiting for
- Current market conditions
- Color-coded status indicators

### System Logs
Detailed execution log showing:
- Connection events
- Strategy execution steps
- Error messages
- Trade confirmations

## Auto Mode Operation

### Starting Auto Mode
1. Ensure MT5 connection is active
2. Click "Run Strategy (Auto)"
3. System begins continuous monitoring every 2 seconds
4. Button changes to "Auto Mode Running..." and becomes disabled

### What Auto Mode Does
1. Continuous Monitoring: Checks market conditions every 2 seconds
2. State Progression: Automatically moves through trading workflow
3. Trade Execution: Places trades when all conditions are met
4. Real-time Updates: Updates dashboard with current status

### Auto Mode Workflow
```
IDLE → SWEPT → CONFIRMED → ARMED → IN_TRADE
```

# Step 1: Sweep Detection
- Monitors price vs Asian range
- Detects when price sweeps beyond threshold
- Records sweep direction and price

# Step 2: Reversal Confirmation
- Waits for price to close back inside Asian range
- Validates M5 displacement (≥1.3×ATR)
- Checks M1 CHOCH pattern

# Step 3: Confluence Check
- Verifies spread ≤2.0 pips
- Checks for LBMA auction blackouts
- Validates market conditions

# Step 4: Signal Generation
- Calculates entry, SL, TP levels
- Determines position size (1% risk)
- Prepares trade signal

# Step 5: Trade Execution
- Places market order with SL/TP
- Confirms execution
- Continues monitoring for next opportunity

### Stopping Auto Mode
1. Click "Stop Auto Mode" button
2. System stops continuous monitoring
3. Returns to manual control mode
4. Button disappears, "Run Strategy (Auto)" becomes available

## Manual Trading Steps

### Step-by-Step Manual Execution

1. Initialize Session
- Creates new trading session or loads existing
- Calculates Asian range for current day
- Sets initial state to IDLE

2. Detect Sweep
- Monitors current price vs Asian range
- Identifies liquidity sweeps beyond threshold
- Records sweep details and updates state to SWEPT

3. Confirm Reversal
- Waits for price to return inside Asian range
- Validates reversal criteria
- Updates state to CONFIRMED when ready

4. Generate Signal
- Creates trade signal with risk parameters
- Calculates SL/TP levels
- Updates state to ARMED

5. Execute Trade
- Places market order
- Confirms execution
- Updates state to IN_TRADE

## Understanding Status Messages

### System Status Colors
- Blue: Information/Processing
- Green: Success/Ready
- Yellow: Warning/Attention needed
- Purple: Waiting for conditions
- Red: Error/Issue

### Common Status Messages

# "Waiting for price to close back inside Asian range (M5)"
- System detected sweep but price hasn't returned to range
- Waiting for M5 candle to close inside Asian boundaries
- This is normal - be patient

# "Waiting for reversal confirmation"
- Price is back inside range
- System is validating reversal criteria
- Checking displacement and CHOCH patterns

# "Market conditions not suitable (spread/auction time)"
- Spread is too wide (>2.0 pips)
- Currently in LBMA auction blackout period
- Wait for better conditions

# "Strategy stage: [STAGE]"
- Shows current progress through workflow
- Indicates what step system is on
- Normal progression indicator

## Troubleshooting

### Connection Issues
# "Failed to connect to MT5"
- Check account credentials
- Ensure MT5 terminal is running
- Verify server name is correct
- Check internet connection

# "MT5 initialize failed"
- Restart MT5 terminal
- Check if terminal is accessible
- Verify Python MetaTrader5 package installation

### Strategy Issues
# "Invalid state: SWEPT"
- Normal when trying to detect sweep in SWEPT state
- Use "Confirm Reversal" or "Run Strategy (Auto)" instead
- System is working correctly

# "Price not back inside Asian range"
- Normal waiting condition
- Price will eventually return to range
- Monitor M5 timeframe for close

# "Reversal not confirmed"
- Check specific reason in logs
- Usually waiting for price action
- Normal part of validation process

### Performance Issues
Slow response times
- Check internet connection
- Monitor system resources
- Consider reducing monitoring frequency
- Restart system if needed

## Best Practices

### 1. Session Management
- Initialize session at start of trading day
- Don't reinitialize during active session
- Monitor session status regularly

### 2. Auto Mode Usage
- Start auto mode when ready to trade
- Monitor system status for updates
- Stop auto mode when not trading
- Use manual mode for testing

### 3. Risk Management
- Always use demo account first
- Monitor position sizes
- Check SL/TP levels before execution
- Review trade confirmations

### 4. System Monitoring
- Watch system status updates
- Monitor logs for errors
- Check connection status
- Verify Asian range data

## Advanced Features

### Custom Parameters
- Asian session times (configurable)
- Risk percentage (default 1%)
- Stop loss pips (default 5)
- ATR multiplier (default 1.3)

### Data Analysis
- Historical sweep analysis
- Performance metrics
- Risk/reward ratios
- Win rate tracking

### Integration Options
- Webhook notifications
- Email alerts
- Telegram bot integration
- Custom API endpoints

## Support & Maintenance

### Regular Tasks
- Monitor system logs
- Check connection status
- Review performance metrics
- Update parameters as needed

### System Updates
- Keep Python packages updated
- Monitor for MT5 updates
- Backup configuration files
- Test new features in demo

### Getting Help
- Check system logs for errors
- Review this manual
- Contact development team
- Check system documentation

## Risk Warnings

# ⚠️ Important Disclaimers
- This system is for educational purposes
- Trading involves substantial risk
- Past performance doesn't guarantee future results
- Always test in demo environment first
- Never risk more than you can afford to lose
- Monitor system performance continuously
- Have backup trading methods available
