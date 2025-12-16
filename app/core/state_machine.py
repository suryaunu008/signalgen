"""
State Machine Module

This module provides engine state management for the SignalGen scalping system.
It manages the state transitions to prevent signal noise and spam.

State Flow:
WAIT → SIGNAL → COOLDOWN → WAIT

Key Features:
- Prevents signal noise through cooldown periods
- Thread-safe state management
- Configurable cooldown durations
- State transition logging

States:
- WAIT: Engine is waiting for valid signal conditions
- SIGNAL: Signal has been generated and being processed
- COOLDOWN: Engine is in cooldown period after signal

Typical Usage:
    state_machine = StateMachine()
    if state_machine.can_generate_signal():
        # Generate signal
        state_machine.transition_to_signal()
        state_machine.start_cooldown(60)  # 60 second cooldown
"""

from enum import Enum
import time
import threading

class EngineState(Enum):
    """Enumeration of possible engine states."""
    WAIT = "wait"
    SIGNAL = "signal"
    COOLDOWN = "cooldown"

class StateMachine:
    """
    State machine for managing scalping engine states and preventing signal noise.
    
    This class ensures that signals are not generated too frequently and
    manages the lifecycle of signal generation with cooldown periods.
    """
    
    def __init__(self, default_cooldown: int = 60):
        """
        Initialize state machine with default cooldown period.
        
        Args:
            default_cooldown: Default cooldown period in seconds
        """
        self._state = EngineState.WAIT
        self._cooldown_end_time = 0
        self._default_cooldown = default_cooldown
        self._lock = threading.Lock()
    
    @property
    def current_state(self) -> EngineState:
        """
        Get the current engine state.
        
        Returns:
            EngineState: Current state of the engine
        """
        with self._lock:
            # Auto-transition from cooldown to wait if cooldown period has ended
            if self._state == EngineState.COOLDOWN and time.time() >= self._cooldown_end_time:
                self._state = EngineState.WAIT
            return self._state
    
    def can_generate_signal(self) -> bool:
        """
        Check if engine can generate a new signal.
        
        Returns:
            bool: True if signal can be generated, False otherwise
        """
        return self.current_state == EngineState.WAIT
    
    def transition_to_signal(self) -> bool:
        """
        Transition to SIGNAL state.
        
        Returns:
            bool: True if transition successful, False otherwise
        """
        with self._lock:
            if self._state == EngineState.WAIT:
                self._state = EngineState.SIGNAL
                return True
            return False
    
    def start_cooldown(self, cooldown_seconds: int = None) -> bool:
        """
        Start cooldown period.
        
        Args:
            cooldown_seconds: Custom cooldown duration, uses default if None
            
        Returns:
            bool: True if cooldown started successfully, False otherwise
        """
        with self._lock:
            if self._state == EngineState.SIGNAL:
                cooldown = cooldown_seconds or self._default_cooldown
                self._cooldown_end_time = time.time() + cooldown
                self._state = EngineState.COOLDOWN
                return True
            return False
    
    def force_wait_state(self) -> None:
        """Force transition to WAIT state (for manual reset)."""
        with self._lock:
            self._state = EngineState.WAIT
            self._cooldown_end_time = 0
    
    def get_remaining_cooldown(self) -> float:
        """
        Get remaining cooldown time in seconds.
        
        Returns:
            float: Remaining cooldown time, 0 if not in cooldown
        """
        with self._lock:
            if self.current_state == EngineState.COOLDOWN:
                return max(0, self._cooldown_end_time - time.time())
            return 0
    
    def get_state_info(self) -> dict:
        """
        Get comprehensive state information.
        
        Returns:
            dict: Current state and additional information
        """
        return {
            'state': self.current_state.value,
            'can_generate_signal': self.can_generate_signal(),
            'remaining_cooldown': self.get_remaining_cooldown()
        }