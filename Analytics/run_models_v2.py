#!/usr/bin/env python3
"""Run MoneyPuck-backed v2 PK Decision Lab models."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime

from db import DatabaseConnection
from models.model_utils import json_safe
from models_v2.moneypuck_pk_models import (
    BayesianPkPlayerEvaluationModel,
    BlockedShotAftershockModel,
    GoalieControlAboveExpectedModel,
    PkFatigueTimingModel,
    PuckMovementGeometryModel,
    RushSetDefenseModel,
    ShortHandedTwoWayValueModel,
)


logger = logging.getLogger(__name__)


MODEL_CLASSES = [
    PuckMovementGeometryModel,
    BlockedShotAftershockModel,
    GoalieControlAboveExpectedModel,
    PkFatigueTimingModel,
    ShortHandedTwoWayValueModel,
    BayesianPkPlayerEvaluationModel,
    RushSetDefenseModel,
]


def main():
    os.makedirs("models/output", exist_ok=True)
    db = DatabaseConnection()
    db.connect()
    started_at = datetime.now()
    results = {}

    try:
        for model_cls in MODEL_CLASSES:
            model = model_cls(db)
            name = model_cls.__name__
            logger.info("\n%s", "=" * 60)
            logger.info("Running %s", name)
            logger.info("%s", "=" * 60)
            results[name] = model.run()

        payload = {
            "version": "moneypuck_v2",
            "source": {
                "name": "MoneyPuck",
                "url": "https://www.moneypuck.com/data.htm",
                "credit": "MoneyPuck.com downloadable CSV data",
            },
            "started_at": started_at.isoformat(),
            "completed_at": datetime.now().isoformat(),
            "models": results,
        }
        path = f"models/output/models_v2_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(json_safe(payload), f, indent=2)
        logger.info("Combined v2 output: %s", path)
        return payload
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    main()
