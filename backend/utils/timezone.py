# backend/utils/timezone.py
from datetime import datetime
import pytz
from ..models.system import get_setting

def get_system_timezone():
    timezone_str = get_setting('timezone', 'UTC')
    try:
        return pytz.timezone(timezone_str)
    except:
        return pytz.UTC

def utc_to_local(utc_dt):
    if utc_dt is None:
        return None
    if utc_dt.tzinfo is None:
        utc_dt = pytz.UTC.localize(utc_dt)
    local_tz = get_system_timezone()
    return utc_dt.astimezone(local_tz)

def format_relative_time(dt):
    if dt is None:
        return 'Just now'
    
    if hasattr(dt, 'tzinfo') and dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)
    elif not hasattr(dt, 'tzinfo'):
        return str(dt)
    
    now = datetime.now(pytz.UTC)
    diff = now - dt
    seconds = diff.total_seconds()
    
    if seconds < 60:
        return 'Just now'
    elif seconds < 120:
        return '1 minute ago'
    elif seconds < 3600:
        return f'{int(seconds // 60)} minutes ago'
    elif seconds < 7200:
        return '1 hour ago'
    elif seconds < 86400:
        return f'{int(seconds // 3600)} hours ago'
    elif seconds < 172800:
        return 'Yesterday'
    elif seconds < 2592000:
        return f'{int(seconds // 86400)} days ago'
    else:
        local_dt = utc_to_local(dt)
        return local_dt.strftime('%b %d, %Y')

def format_local_time(dt, format_str='%b %d, %Y at %I:%M %p'):
    if dt is None:
        return ''
    local_dt = utc_to_local(dt)
    return local_dt.strftime(format_str)