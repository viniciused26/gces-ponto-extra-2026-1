"""Agendamento de polling diário das Centrais de Resultados."""

from __future__ import annotations

import argparse
import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from src.config import get_settings
from src.pipeline import IngestionPipeline

logger = logging.getLogger(__name__)


def run_poll_job() -> None:
    logger.info("Iniciando job de polling agendado")
    pipeline = IngestionPipeline()
    results = pipeline.poll_companies()
    processed = sum(1 for item in results if item.status.value == "processed")
    skipped = sum(1 for item in results if item.status.value == "skipped")
    failed = sum(1 for item in results if item.status.value == "failed")
    logger.info("Polling concluído: processed=%s skipped=%s failed=%s", processed, skipped, failed)


def start_scheduler(interval_hours: int | None = None) -> None:
    settings = get_settings()
    hours = interval_hours or settings.poll_interval_hours

    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_poll_job,
        trigger=IntervalTrigger(hours=hours),
        id="ri-polling",
        replace_existing=True,
    )

    logger.info("Scheduler iniciado — polling a cada %s hora(s). Ctrl+C para encerrar.", hours)
    run_poll_job()
    scheduler.start()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Scheduler de polling RI.")
    parser.add_argument(
        "--interval-hours",
        type=int,
        help="Intervalo entre varreduras (default: POLL_INTERVAL_HOURS ou 24)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Executa uma varredura imediata e encerra (sem agendar)",
    )
    args = parser.parse_args()

    if args.once:
        run_poll_job()
        return

    start_scheduler(interval_hours=args.interval_hours)


if __name__ == "__main__":
    main()
