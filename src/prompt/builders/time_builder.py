from datetime import datetime, timezone
from typing import Dict


class TimeProvider:
    """Time information provider"""

    @staticmethod
    def get_current_time_info(timezone_name: str = "Australia/Adelaide") -> Dict[str, str]:
        """Get current time information"""
        try:
            import pytz
            tz = pytz.timezone(timezone_name)
            now = datetime.now(tz)
        except ImportError:
            now = datetime.now(timezone.utc)

        return {
            "current_date": now.strftime("%Y-%m-%d"),
            "current_time": now.strftime("%H:%M"),
            "current_datetime": now.strftime("%Y-%m-%d %H:%M"),
            "day_of_week": now.strftime("%A"),
            "day_of_week_en": TimeProvider._get_english_weekday(now.weekday()),
            "season": TimeProvider._get_season(now.month),
            "time_period": TimeProvider._get_time_period(now.hour),
            "timestamp": now.isoformat(),
        }

    @staticmethod
    def _get_english_weekday(weekday: int) -> str:
        """Get English weekday"""
        weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        return weekdays[weekday]

    @staticmethod
    def _get_season(month: int) -> str:
        """Get season (Southern Hemisphere - Adelaide)"""
        if month in [12, 1, 2]:
            return "Summer"
        elif month in [3, 4, 5]:
            return "Autumn"
        elif month in [6, 7, 8]:
            return "Winter"
        else:
            return "Spring"

    @staticmethod
    def _get_time_period(hour: int) -> str:
        """Get time period"""
        if 5 <= hour < 8:
            return "Early Morning"
        elif 8 <= hour < 12:
            return "Morning"
        elif 12 <= hour < 14:
            return "Noon"
        elif 14 <= hour < 17:
            return "Afternoon"
        elif 17 <= hour < 20:
            return "Evening"
        elif 20 <= hour < 22:
            return "Night"
        else:
            return "Late Night"
