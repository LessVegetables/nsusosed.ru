"""Questionnaire versions.

Each version is a package with its own questions.json, scoring.json and scorer; nothing is
shared between versions, so an old one keeps working exactly as it did. Answers are stored
with their version, and two people are only ever scored on a version they both answered.

To ship a new questionnaire: copy v1 to v2, change it, register it below and bump CURRENT.
People on the old version are then asked to answer again (questionnaire_complete turns false).
"""

from __future__ import annotations
from app.questionnaires import v1

VERSIONS = {1: v1}
CURRENT = 1


def get(version: int):
    return VERSIONS.get(version)


def current():
    return VERSIONS[CURRENT]
