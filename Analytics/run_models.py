#!/usr/bin/env python3
"""Run analytics Models 2-10."""

import json
import logging
import os
from datetime import datetime

from db import DatabaseConnection
from models.model2_pk_rush_commitment import PkRushCommitmentModel
from models.model4_pk_forecheck_structure import PkForecheckStructureModel
from models.model5_pk_faceoff import PkFaceoffModel
from models.model3_clearance_faceoff import IntentionalClearanceFaceoffModel
from models.model6_forward_forechecking import ForwardForecheckingModel
from models.model7_defense_gap_control import DefenseGapControlModel
from models.model8_forward_shot_suppression import ForwardShotSuppressionModel
from models.model9_center_faceoff_value import CenterFaceoffValueModel
from models.model10_net_front_defense import NetFrontDefenseModel
from models.model_utils import ensure_player_scouting_table, json_safe


logger = logging.getLogger(__name__)


MODEL_CLASSES = [
    PkRushCommitmentModel,
    IntentionalClearanceFaceoffModel,
    PkForecheckStructureModel,
    PkFaceoffModel,
    ForwardForecheckingModel,
    DefenseGapControlModel,
    ForwardShotSuppressionModel,
    CenterFaceoffValueModel,
    NetFrontDefenseModel,
]


STALE_SCOUTING_MODEL_NAMES = [
    "model6_forward_forechecking",
    "model7_defense_gap_control",
    "model8_forward_shot_suppression",
    "model10_net_front_defense",
]


def clean_stale_scouting_rows(db):
    """Remove rows produced by earlier unsupported on-ice scouting models."""
    ensure_player_scouting_table(db)
    for model_name in STALE_SCOUTING_MODEL_NAMES:
        deleted = db.execute("DELETE FROM player_scouting WHERE model_name = %s", (model_name,))
        if deleted:
            logger.info("Removed %s stale player_scouting rows for %s", deleted, model_name)


def main():
    os.makedirs("models/output", exist_ok=True)
    db = DatabaseConnection()
    db.connect()
    started_at = datetime.now()
    results = {}

    try:
        clean_stale_scouting_rows(db)

        for model_cls in MODEL_CLASSES:
            model = model_cls(db)
            name = model_cls.__name__
            logger.info("\n%s", "=" * 60)
            logger.info("Running %s", name)
            logger.info("%s", "=" * 60)
            results[name] = model.run()

        payload = {
            "started_at": started_at.isoformat(),
            "completed_at": datetime.now().isoformat(),
            "models": results,
        }
        path = f"models/output/models_2_10_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(json_safe(payload), f, indent=2)
        logger.info("Combined Models 2-10 output: %s", path)
        return payload
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    main()
