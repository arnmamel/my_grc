from __future__ import annotations

import boto3


def build_session(profile_name: str, region_name: str):
    return boto3.Session(profile_name=profile_name, region_name=region_name)

