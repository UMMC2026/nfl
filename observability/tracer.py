"""
FUOOM Tracing Layer
==================
Distributed tracing for pipeline execution.

Usage:
    from observability import tracer
    
    with tracer.span("analyze_slate", sport="NBA") as span:
        span.set_attribute("player_count", 64)
        # ... analysis code ...
        span.add_event("validation_complete")
"""

import time
import threading
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from contextlib import contextmanager
from pathlib import Path
import json

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False


class SpanContext:
    """Lightweight span context for tracing."""
    
    def __init__(self, name: str, tracer: 'FUOOMTracer', parent_id: Optional[str] = None):
        self.span_id = str(uuid.uuid4())[:8]
        self.name = name
        self.parent_id = parent_id
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.attributes: Dict[str, Any] = {}
        self.events: List[Dict[str, Any]] = []
        self.status = "OK"
        self.tracer = tracer
    
    def set_attribute(self, key: str, value: Any):
        """Set a span attribute."""
        self.attributes[key] = value
        return self
    
    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """Add an event to the span."""
        self.events.append({
            "name": name,
            "timestamp": time.time() - self.start_time,
            "attributes": attributes or {}
        })
        return self
    
    def set_error(self, error: Exception):
        """Mark span as errored."""
        self.status = "ERROR"
        self.set_attribute("error.type", type(error).__name__)
        self.set_attribute("error.message", str(error))
        return self
    
    def end(self):
        """End the span."""
        self.end_time = time.time()
        self.tracer._record_span(self)
    
    @property
    def duration_ms(self) -> float:
        """Get duration in milliseconds."""
        end = self.end_time or time.time()
        return (end - self.start_time) * 1000
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "span_id": self.span_id,
            "name": self.name,
            "parent_id": self.parent_id,
            "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
            "duration_ms": self.duration_ms,
            "status": self.status,
            "attributes": self.attributes,
            "events": self.events,
        }
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.set_error(exc_val)
        self.end()


class FUOOMTracer:
    """
    Distributed tracing for FUOOM pipelines.
    Works with or without OpenTelemetry.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._initialized = True
        self._traces: Dict[str, List[SpanContext]] = {}
        self._current_trace_id: Optional[str] = None
        self._span_stack: List[SpanContext] = []
        self._trace_file = Path("observability/traces.json")
        self._trace_file.parent.mkdir(exist_ok=True)
        
        # Initialize OpenTelemetry if available
        if OTEL_AVAILABLE:
            provider = TracerProvider()
            # Optional: Add console exporter for debugging
            # processor = SimpleSpanProcessor(ConsoleSpanExporter())
            # provider.add_span_processor(processor)
            trace.set_tracer_provider(provider)
            self._otel_tracer = trace.get_tracer("fuoom")
        else:
            self._otel_tracer = None
    
    def start_trace(self, name: str = None) -> str:
        """Start a new trace."""
        trace_id = str(uuid.uuid4())[:16]
        self._current_trace_id = trace_id
        self._traces[trace_id] = []
        self._span_stack = []
        return trace_id
    
    def span(self, name: str, **attributes) -> SpanContext:
        """
        Create a new span.
        
        Usage:
            with tracer.span("analyze_player", player="LeBron") as span:
                span.add_event("data_loaded")
                # ... do work ...
        """
        # Ensure we have a trace
        if not self._current_trace_id:
            self.start_trace()
        
        # Get parent from stack
        parent_id = self._span_stack[-1].span_id if self._span_stack else None
        
        span = SpanContext(name, self, parent_id)
        
        # Set initial attributes
        for key, value in attributes.items():
            span.set_attribute(key, value)
        
        self._span_stack.append(span)
        return span
    
    def _record_span(self, span: SpanContext):
        """Record a completed span."""
        if self._current_trace_id:
            self._traces[self._current_trace_id].append(span.to_dict())
        
        # Remove from stack
        if self._span_stack and self._span_stack[-1] == span:
            self._span_stack.pop()
    
    def end_trace(self) -> Optional[Dict[str, Any]]:
        """End the current trace and return summary."""
        if not self._current_trace_id:
            return None
        
        trace_id = self._current_trace_id
        spans = self._traces.get(trace_id, [])
        
        summary = {
            "trace_id": trace_id,
            "timestamp": datetime.now().isoformat(),
            "span_count": len(spans),
            "spans": spans,
            "total_duration_ms": sum(s.get("duration_ms", 0) for s in spans),
        }
        
        # Save to file
        self._save_trace(summary)
        
        self._current_trace_id = None
        self._span_stack = []
        
        return summary
    
    def _save_trace(self, trace_summary: Dict[str, Any]):
        """Save trace to file."""
        traces = []
        if self._trace_file.exists():
            try:
                with open(self._trace_file) as f:
                    traces = json.load(f)
            except:
                pass
        
        traces.append(trace_summary)
        traces = traces[-100:]  # Keep last 100 traces
        
        with open(self._trace_file, 'w') as f:
            json.dump(traces, f, indent=2)
    
    def get_current_trace(self) -> Optional[List[Dict[str, Any]]]:
        """Get spans from current trace."""
        if self._current_trace_id:
            return self._traces.get(self._current_trace_id, [])
        return None
    
    def print_trace(self, trace_id: Optional[str] = None):
        """Print a formatted trace."""
        tid = trace_id or self._current_trace_id
        if not tid or tid not in self._traces:
            print("No trace found")
            return
        
        spans = self._traces[tid]
        
        print("\n" + "=" * 60)
        print(f"  🔍 TRACE: {tid}")
        print("=" * 60)
        
        # Build tree structure
        root_spans = [s for s in spans if s.get("parent_id") is None]
        
        def print_span(span: Dict, indent: int = 0):
            prefix = "  " * indent
            status_icon = "✅" if span["status"] == "OK" else "❌"
            print(f"{prefix}{status_icon} {span['name']} ({span['duration_ms']:.1f}ms)")
            
            # Print attributes
            for key, value in span.get("attributes", {}).items():
                print(f"{prefix}   • {key}: {value}")
            
            # Print events
            for event in span.get("events", []):
                print(f"{prefix}   📌 {event['name']} (+{event['timestamp']*1000:.0f}ms)")
            
            # Print children
            children = [s for s in spans if s.get("parent_id") == span["span_id"]]
            for child in children:
                print_span(child, indent + 1)
        
        for root in root_spans:
            print_span(root)
        
        total_ms = sum(s.get("duration_ms", 0) for s in root_spans)
        print(f"\n⏱️  Total Duration: {total_ms:.1f}ms")
        print("=" * 60)


# Singleton accessor
_tracer_instance: Optional[FUOOMTracer] = None

def get_tracer() -> FUOOMTracer:
    """Get the singleton tracer instance."""
    global _tracer_instance
    if _tracer_instance is None:
        _tracer_instance = FUOOMTracer()
    return _tracer_instance
