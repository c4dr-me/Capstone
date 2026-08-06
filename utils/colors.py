"""Color palette for ResolveOne enterprise design system."""

COLORS = {
    "primary": "#2563EB",
    "primary_light": "#DBEAFE",
    "primary_dark": "#1E40AF",
    "success": "#10b981",
    "warning": "#f59e0b",
    "critical": "#ef4444",
    "info": "#3b82f6",
    "neutral_50": "#f9fafb",
    "neutral_100": "#f3f4f6",
    "neutral_200": "#e5e7eb",
    "neutral_500": "#6b7280",
    "neutral_700": "#374151",
    "neutral_900": "#111827",
}

PRIORITY_COLORS = {
    "Critical": "#ef4444",
    "High": "#f59e0b",
    "Medium": "#3b82f6",
    "Low": "#10b981",
}

STATUS_COLORS = {
    "Pending": "#f59e0b",
    "In Review": "#3b82f6",
    "Resolved": "#10b981",
    "Escalated": "#ef4444",
}

EXCEPTION_TYPE_COLORS = {
    "INSUFFICIENT_BALANCE": "#ef4444",
    "BAD_PIN": "#f59e0b",
    "TECHNICAL_GLITCH": "#3b82f6",
    "BAD_CARD_NUMBER": "#8b5cf6",
    "BAD_CVV": "#ec4899",
    "BAD_EXPIRATION": "#06b6d4",
    "BAD_ZIPCODE": "#10b981",
}

def get_priority_color(priority):
    """Get color for priority level."""
    return PRIORITY_COLORS.get(priority, COLORS["neutral_500"])

def get_status_color(status):
    """Get color for status."""
    return STATUS_COLORS.get(status, COLORS["neutral_500"])

def get_exception_color(exception_type):
    """Get color for exception type."""
    return EXCEPTION_TYPE_COLORS.get(exception_type, COLORS["neutral_500"])

def rgb_to_hex(r, g, b):
    """Convert RGB to hex."""
    return f"#{r:02x}{g:02x}{b:02x}"

def hex_to_rgb(hex_color):
    """Convert hex to RGB."""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
