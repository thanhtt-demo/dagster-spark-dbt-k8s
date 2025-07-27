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
import psycopg2
import pandas as pd

t24_partitions = DynamicPartitionsDefinition(name="t24")
way4_partitions = DynamicPartitionsDefinition(name="way4")


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

        # Track new partitions to add
        t24_partitions_to_add = []
        way4_partitions_to_add = []

        # Check calendar records and prepare partitions to add
        for system_name, lwd in calendar_records:
            lwd_str = lwd.strftime("%Y-%m-%d")

            if system_name == "t24" and lwd_str not in t24_existing_partitions:
                t24_partitions_to_add.append(lwd_str)
                context.log.info(f"Found new t24 partition to add: {lwd_str}")

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
    conn = psycopg2.connect(
        host="dagster-postgresql.dagster-python.svc.cluster.local",
        port="5432",
        database="dagster",
        user="dagster",  # Replace with actual username if different
        password="dagster",  # Replace with actual password if different
    )
    return conn


# Asset to create the table if not exists
@asset
def create_working_day_calendar_table(context: AssetExecutionContext):
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
    except Exception as e:
        conn.rollback()
        context.log.error(f"Error creating table: {str(e)}")
        raise
    finally:
        cursor.close()
        conn.close()


# Asset to update working day calendar daily
@asset(description="Updates working_day_calendar table with today's data")
def update_working_day_calendar(context: AssetExecutionContext):
    """Insert today's data into working_day_calendar table"""
    conn = get_postgres_connection()
    cursor = conn.cursor()

    try:
        # Systems to update
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
        context.log.error(f"Error updating working day calendar: {str(e)}")
        raise
    finally:
        cursor.close()
        conn.close()


# Schedule definition for daily update
working_day_schedule = ScheduleDefinition(
    job_name="update_working_day_calendar_job",
    cron_schedule="0 0 * * *",  # Run at midnight every day
    execution_timezone="UTC",
)


# Define job for the working day calendar update
@job
def update_working_day_calendar_job():
    create_working_day_calendar_table()
    update_working_day_calendar()


# Update Definitions to include new assets, jobs and schedules
defs = Definitions(
    assets=[
        iris_dataset_size,
        create_working_day_calendar_table,
        update_working_day_calendar,
    ],
    sensors=[update_dynamic_partition_sensor],
    jobs=[update_working_day_calendar_job],
    schedules=[working_day_schedule]
)
