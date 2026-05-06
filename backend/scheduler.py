import logging
import threading
import time
import traceback
from datetime import date, datetime, timedelta

_logger = logging.getLogger(__name__)

_scheduler_started = False
_scheduler_thread = None


def start_scheduler(app):
    """启动后台定时任务（在app启动时调用）"""
    global _scheduler_started, _scheduler_thread

    if _scheduler_started:
        return

    _scheduler_started = True

    def _run():
        """后台线程：每周日晚上22:00执行AI周报生成"""
        _logger.info('Scheduler thread started')
        while True:
            try:
                now = datetime.now()
                # 计算下次执行时间：下周日 22:00
                days_until_sunday = (6 - now.weekday()) % 7
                if days_until_sunday == 0 and now.hour >= 22:
                    days_until_sunday = 7  # 本周日已经过了22点，等下周日
                next_run = now.replace(hour=22, minute=0, second=0, microsecond=0) + timedelta(days=days_until_sunday)
                
                sleep_seconds = (next_run - now).total_seconds()
                _logger.info(f'Next insight generation scheduled at {next_run} (in {sleep_seconds:.0f}s)')
                
                time.sleep(sleep_seconds)

                # 执行周报生成
                _logger.info('Starting weekly insight generation...')
                try:
                    from ai_insight import generate_insights_for_all_members
                    with app.app_context():
                        count = generate_insights_for_all_members()
                    _logger.info(f'Weekly insight generation done: {count} insights generated')
                except Exception:
                    _logger.error(f'Weekly insight generation failed: {traceback.format_exc()}')
                    
            except Exception:
                _logger.error(f'Scheduler error: {traceback.format_exc()}')
                time.sleep(3600)  # 出错后1小时重试

    _scheduler_thread = threading.Thread(target=_run, daemon=True)
    _scheduler_thread.start()
    _logger.info('Scheduler initialized')
