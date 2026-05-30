"""
백엔드 콘솔 로깅 설정.
- LOG_LEVEL 환경변수로 레벨 조정 (DEBUG/INFO/WARNING/ERROR, 기본 INFO)
- LOG_FILE 환경변수로 파일 로깅 활성화 (기본: logs/agent.log)
- 카테고리 prefix를 통일된 포맷으로 출력해 단계/이슈/알람/경고/오류/누락을 한눈에 확인.
"""
import logging
import logging.handlers
import os
import sys

LOG_LEVEL = (os.getenv("LOG_LEVEL") or "INFO").upper()
LOG_FILE = os.getenv("LOG_FILE") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "agent.log")

_FMT = "%(asctime)s [%(levelname)-5s] %(name)-10s | %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"

_initialized = False


def setup_logging():
    global _initialized
    if _initialized:
        return
    root = logging.getLogger("agent")
    root.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    root.propagate = False

    # 콘솔 핸들러 (stderr)
    ch = logging.StreamHandler(stream=sys.stderr)
    ch.setLevel(root.level)
    ch.setFormatter(logging.Formatter(_FMT, datefmt=_DATEFMT))
    root.addHandler(ch)

    # 파일 핸들러 (rotation: 5MB × 5)
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(
            LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        fh.setLevel(root.level)
        fh.setFormatter(logging.Formatter(_FMT, datefmt=_DATEFMT))
        root.addHandler(fh)
    except Exception as e:
        root.warning(f"파일 로깅 초기화 실패: {e} → 콘솔만 사용")

    # 너무 시끄러운 외부 로거 톤다운
    for noisy in ("urllib3", "httpx", "httpcore", "google", "grpc", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _initialized = True


def get_logger(name: str) -> logging.Logger:
    """모듈/카테고리별 로거. 예) get_logger('STAGE3'), get_logger('AUTH')"""
    setup_logging()
    return logging.getLogger(f"agent.{name}")


# 카테고리 prefix를 메시지에 명시적으로 포함시키는 헬퍼들
def log_event(category: str, level: str, msg: str, **fields):
    """카테고리 + 키=값 형태로 통일된 1줄 로그."""
    lg = get_logger(category)
    extra = ""
    if fields:
        extra = " | " + " ".join(f"{k}={v}" for k, v in fields.items())
    getattr(lg, level.lower(), lg.info)(f"{msg}{extra}")
