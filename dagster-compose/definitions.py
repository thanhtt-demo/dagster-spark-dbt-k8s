from pydantic import Field
from typing import List
from dagster import (
    asset,
    job,
    op,
    AssetsDefinition,
    AssetExecutionContext,
    AssetCheckExecutionContext,
    Config,
    DynamicPartitionsDefinition,
    ScheduleDefinition,
    Definitions,
    sensor,
    SensorEvaluationContext,
    asset_check,
    AssetCheckResult,
    In,
    Out,
    Nothing,
    JobDefinition,
    DailyPartitionsDefinition,
    asset_check,
    AssetCheckResult,
    AssetCheckSeverity,
    AssetKey,
    EventRecordsFilter,
    DagsterEventType,
)
from dagster import SensorResult, AddDynamicPartitionsRequest
from datetime import datetime, timedelta
import psycopg2
import pandas as pd
import os

t24_partitions = DynamicPartitionsDefinition(name="t24")
way4_partitions = DynamicPartitionsDefinition(name="way4")
t24month_partitions = DynamicPartitionsDefinition(name="t24month")
daily_partitions_def = DailyPartitionsDefinition(start_date="2025-01-01")


@asset(partitions_def=t24_partitions, description="description for t24 asset.--")
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

    row_count = df.shape[0]
    context.log.info(f"Loaded {row_count} data points.")

    # Add metadata that will be used by the asset check
    context.add_output_metadata(
        {
            "row_count": row_count,
            "columns": len(df.columns),
            "species_count": df["species"].nunique(),
        }
    )


class PrefixConfig(Config):
    asset_prefix: str = Field(
        description="Prefix to filter asset keys",
        default="prefix...",
        examples=["iris", "t24", "way4"],
    )
    var2: str = Field(
        default="abcdef",
        description="Đây là một biến tùy chỉnh",
        examples=["abcexample1", "abcexample2"],
        min_length=6,
        pattern="^abc.*"
    )


@op
def collect_asset_keys_using_config(context, config: PrefixConfig):
    """
    Truy vấn **event-log** để lấy tất cả các `AssetKey`
    rồi lọc theo `asset_prefix`.
    Launchpad:
    ops:
    collect_asset_keys:
        inputs:
        asset_prefix: irsss

    """
    assert config.asset_prefix == "iris"
    asset_prefix = config.asset_prefix
    context.log.info(f"Received input_value: {asset_prefix}")
    # Lấy records materialization để sinh danh sách AssetKey hiện có
    records = context.instance.get_event_records(
        EventRecordsFilter(event_type=DagsterEventType.ASSET_MATERIALIZATION)
    )
    # Lấy toàn bộ AssetKey từng materialize:
    all_keys = {rec.asset_key for rec in records}

    prefix = asset_prefix
    matched = [
        key.to_user_string()
        for key in all_keys
        if key.to_user_string().startswith(prefix)
    ]

    context.log.info(f"Matched asset keys: {matched}")

    return matched


@job
def asset_prefix_job_using_config():
    """Job trả về danh sách AssetKey thỏa mãn tiền tố."""
    collect_asset_keys_using_config()


@asset_check(
    asset=AssetKey(
        "iris_dataset_size"
    ),  # hoặc truyền thẳng biến assets: iris_dataset_size
    name="test_asset_check",
    description="Fail nếu row_count = 0 dựa trên output_metadata",
)
def test_asset_check(context):
    key = AssetKey("iris_dataset_size")  # hoặc AssetKey.from_user_string(...)

    # Lấy materialization mới nhất của asset
    mat_event = context.instance.get_latest_materialization_event(
        asset_key=key
    )  # :contentReference[oaicite:0]{index=0}
    if not mat_event:
        return AssetCheckResult(
            passed=False,
            severity=AssetCheckSeverity.ERROR,
            metadata={"reason": "No materialization yet"},
        )

    # Lấy metadata 'row_count'
    row_meta = mat_event.dagster_event.event_specific_data.materialization.metadata.get(
        "row_count"
    )
    # `row_meta` có thể là MetadataValue – lấy .value nếu có
    row_count = getattr(row_meta, "value", row_meta)

    return AssetCheckResult(
        passed=row_count != 0,
        severity=AssetCheckSeverity.ERROR,
        metadata={"row_count": row_count},
    )


@asset(partitions_def=t24month_partitions)
def iris_monthly_stats(context: AssetExecutionContext) -> None:
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

    partition_key = context.partition_key
    context.log.info(f"Processing monthly statistics for partition: {partition_key}")

    # Calculate monthly statistics (this is just a sample)
    stats = {
        "mean_sepal_length": df["sepal_length_cm"].mean(),
        "mean_sepal_width": df["sepal_width_cm"].mean(),
        "count": len(df),
        "month": partition_key,
    }

    context.log.info(f"Monthly statistics: {stats}")


@sensor(minimum_interval_seconds=30)
def update_dynamic_partition_sensor(context: SensorEvaluationContext):
    """Sensor to add last working days as dynamic partitions for T24 and Way4 systems"""
    conn = get_postgres_connection()
    cursor = conn.cursor()

    try:
        # Query to get all records from working_day_calendar
        cursor.execute("SELECT system_name, lwd FROM working_day_calendar")
        calendar_records = cursor.fetchall()

        # Get existing partitions for both systems
        t24_existing_partitions = context.instance.get_dynamic_partitions("t24")
        way4_existing_partitions = context.instance.get_dynamic_partitions("way4")
        t24month_existing_partitions = context.instance.get_dynamic_partitions(
            "t24month"
        )

        # Track new partitions to add
        t24_partitions_to_add = []
        way4_partitions_to_add = []
        t24month_partitions_to_add = []

        # Check calendar records and prepare partitions to add
        for system_name, lwd in calendar_records:
            lwd_str = lwd.strftime("%Y-%m-%d")

            if system_name == "t24":
                # Handle t24 day partitions
                if lwd_str not in t24_existing_partitions:
                    t24_partitions_to_add.append(lwd_str)
                    context.log.info(f"Found new t24 partition to add: {lwd_str}")

                # Handle t24month partitions (yyyy-mm format)
                lwd_month_str = lwd.strftime("%Y-%m")
                if lwd_month_str not in t24month_existing_partitions:
                    t24month_partitions_to_add.append(lwd_month_str)
                    context.log.info(
                        f"Found new t24month partition to add: {lwd_month_str}"
                    )

            elif system_name == "way4" and lwd_str not in way4_existing_partitions:
                way4_partitions_to_add.append(lwd_str)
                context.log.info(f"Found new way4 partition to add: {lwd_str}")

        # Prepare dynamic partition requests
        dynamic_partitions_requests = []

        if t24_partitions_to_add:
            dynamic_partitions_requests.append(
                AddDynamicPartitionsRequest(
                    partitions_def_name="t24", partition_keys=t24_partitions_to_add
                )
            )

        if way4_partitions_to_add:
            dynamic_partitions_requests.append(
                AddDynamicPartitionsRequest(
                    partitions_def_name="way4", partition_keys=way4_partitions_to_add
                )
            )

        if t24month_partitions_to_add:
            dynamic_partitions_requests.append(
                AddDynamicPartitionsRequest(
                    partitions_def_name="t24month",
                    partition_keys=t24month_partitions_to_add,
                )
            )

        if dynamic_partitions_requests:
            context.log.info(
                f"Adding {len(dynamic_partitions_requests)} dynamic partition requests"
            )
            return SensorResult(dynamic_partitions_requests=dynamic_partitions_requests)
        else:
            context.log.info("No new partitions to add")
            return SensorResult()

    except Exception as e:
        context.log.error(f"Error in t24_partition_sensor: {str(e)}")
        raise
    finally:
        cursor.close()
        conn.close()


# Database connection function
def get_postgres_connection():
    """Create a connection to PostgreSQL database"""
    # Get connection parameters from environment variables
    hostname = "docker_example_postgresql"  # For local connection, might need to change to 'localhost'
    username = os.environ.get("DAGSTER_POSTGRES_USER")
    password = os.environ.get("DAGSTER_POSTGRES_PASSWORD")
    db_name = os.environ.get("DAGSTER_POSTGRES_DB")
    port = 5432

    conn = psycopg2.connect(
        host=hostname,
        port=port,
        database=db_name,
        user=username,
        password=password,
    )
    return conn


# Asset to create the table if not exists
@asset
def working_day_calendar_table(context: AssetExecutionContext):
    """Create the working_day_calendar table if it doesn't exist"""
    conn = get_postgres_connection()
    cursor = conn.cursor()

    try:
        # Create table if not exists
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS working_day_calendar (
            id SERIAL PRIMARY KEY,
            system_name VARCHAR(50) NOT NULL,
            today DATE NOT NULL,
            lwd DATE NOT NULL,
            is_working_day BOOLEAN NOT NULL,
            UNIQUE(system_name, today)
        )
        """
        )
        conn.commit()
        context.log.info("Table working_day_calendar created or already exists")

        systems = ["t24", "way4"]  # Add more systems as needed
        today = datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        is_working_day = True  # Default to true, could be determined by business logic

        for system in systems:
            # Check if entry already exists
            cursor.execute(
                "SELECT id FROM working_day_calendar WHERE system_name = %s AND today = %s",
                (system, today),
            )

            if cursor.fetchone() is None:
                # Insert new record
                cursor.execute(
                    """
                    INSERT INTO working_day_calendar (system_name, today, lwd, is_working_day)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (system, today, yesterday, is_working_day),
                )
                context.log.info(f"Inserted working day record for {system} on {today}")
            else:
                context.log.info(f"Record for {system} on {today} already exists")

        conn.commit()
    except Exception as e:
        conn.rollback()
        context.log.error(f"Error creating table: {str(e)}")
        raise
    finally:
        cursor.close()
        conn.close()


# Utility function to get partition key from asset check context
def get_partition_key(context: AssetCheckExecutionContext) -> str:
    """Extract partition key from asset check context"""
    step_context = context.get_step_execution_context()
    partition = step_context.partition_key
    return partition


# Schedule definition for daily update
working_day_schedule = ScheduleDefinition(
    name="working_day_calendar_update",  # Add a name for the schedule
    cron_schedule="55 9 * * *",  # Run at 9:55 AM every day
    execution_timezone="Asia/Bangkok",
    description="Daily schedule to update the working day calendar",
    target=[working_day_calendar_table],
)


# Update Definitions to include new assets, jobs and schedules
defs = Definitions(
    assets=[iris_dataset_size, iris_monthly_stats, working_day_calendar_table],
    asset_checks=[test_asset_check],
    sensors=[update_dynamic_partition_sensor],
    schedules=[working_day_schedule],
    jobs=[asset_prefix_job_using_config],
)
