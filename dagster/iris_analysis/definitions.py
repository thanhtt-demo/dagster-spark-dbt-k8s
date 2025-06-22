from dagster import (
    asset,
    job,
    op,
    AssetsDefinition,
    AssetExecutionContext,
    Config,
    DynamicPartitionsDefinition,
    ScheduleDefinition,
    Definitions,
    sensor,
    SensorEvaluationContext,
)
from dagster import SensorResult, AddDynamicPartitionsRequest
from datetime import datetime, timedelta

import pandas as pd

t24_partitions = DynamicPartitionsDefinition(name="t24")


@asset(partitions_def=t24_partitions)
def iris_dataset_size(context: AssetExecutionContext) -> None:
    df = pd.read_csv(
        "https://docs.dagster.io/assets/iris.csv",
        names=[
            "sepal_length_cm",
            "sepal_width_cm",
            "petal_length_cm",
            "petal_width_cm",
            "species",
        ],
    )

    context.log.info(f"Loaded {df.shape[0]} data points.")


@sensor(minimum_interval_seconds=30)  # Run once per day
def t24_partition_sensor(context: SensorEvaluationContext):
    """Sensor to add yesterday's date as a new t24 partition"""
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    # Check if partition already exists
    existing_partitions = context.instance.get_dynamic_partitions("t24")

    if yesterday not in existing_partitions:
        context.log.info(f"Adding new t24 partition: {yesterday}")
        return SensorResult(
            dynamic_partitions_requests=[
                AddDynamicPartitionsRequest(
                    partitions_def_name="t24", partition_keys=[yesterday]
                )
            ]
        )
    else:
        context.log.info(f"Partition {yesterday} already exists")
        return SensorResult()


defs = Definitions(assets=[iris_dataset_size], sensors=[t24_partition_sensor])
