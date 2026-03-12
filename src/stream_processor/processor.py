"""
PySpark Stream Processor — reads from Redpanda, detects churn signals,
writes alerts to PostgreSQL.

Run with:  python -m src.stream_processor.processor
"""

import os
import json
from dotenv import load_dotenv

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField,
    StringType, IntegerType, DoubleType, TimestampType,
)

load_dotenv()

# ─── CONFIG ────────────────────────────────────────────────────
REDPANDA_BROKERS          = os.getenv("REDPANDA_BROKERS", "localhost:19092")
TOPIC_NAME                = os.getenv("TOPIC_NAME", "customer-events")
POSTGRES_URL              = os.getenv("POSTGRES_URL", "")
POSTGRES_JDBC_URL         = POSTGRES_URL.replace("postgresql://", "jdbc:postgresql://")
HIGH_RISK_THRESHOLD       = int(os.getenv("HIGH_RISK_SCORE_THRESHOLD", "75"))
CRITICAL_RISK_THRESHOLD   = int(os.getenv("CRITICAL_RISK_SCORE_THRESHOLD", "90"))
CHECKPOINT_DIR            = "/tmp/spark_checkpoints"

# ─── EVENT SCHEMA ──────────────────────────────────────────────
EVENT_SCHEMA = StructType([
    StructField("event_id",           StringType(),  True),
    StructField("customer_id",        StringType(),  False),
    StructField("customer_name",      StringType(),  True),
    StructField("mrr",                DoubleType(),  True),
    StructField("plan",               StringType(),  True),
    StructField("industry",           StringType(),  True),
    StructField("event_type",         StringType(),  False),
    StructField("severity",           StringType(),  True),
    StructField("timestamp",          StringType(),  True),
    StructField("error_type",         StringType(),  True),
    StructField("error_count",        IntegerType(), True),
    StructField("ticket_subject",     StringType(),  True),
    StructField("open_hours",         IntegerType(), True),
    StructField("session_duration_min", IntegerType(), True),
    StructField("features_used",      IntegerType(), True),
])

# ─── SEVERITY SCORING ──────────────────────────────────────────
SEVERITY_SCORES = {"low": 10, "medium": 30, "high": 60, "critical": 90}


def build_spark_session() -> SparkSession:
    return (
        SparkSession.builder
        .appName("RevenueRecoveryEngine")
        .config("spark.jars.packages",
                "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,"
                "org.postgresql:postgresql:42.7.1")
        .config("spark.sql.streaming.checkpointLocation", CHECKPOINT_DIR)
        .config("spark.sql.shuffle.partitions", "4")       # reduce for dev
        .getOrCreate()
    )


def write_alerts_to_postgres(batch_df, epoch_id: int) -> None:
    """
    Called for each micro-batch by PySpark.
    Writes alert records to PostgreSQL.
    """
    if batch_df.isEmpty():
        return

    print(f"[Epoch {epoch_id}] Writing {batch_df.count()} alerts to Postgres")

    (batch_df.write
        .format("jdbc")
        .option("url",      POSTGRES_JDBC_URL)
        .option("dbtable",  "alerts")
        .option("driver",   "org.postgresql.Driver")
        .mode("append")
        .save())


def main():
    print("Starting PySpark Stream Processor...")
    spark = build_spark_session()
    spark.sparkContext.setLogLevel("WARN")

    # ── Step 1: Read raw events from Redpanda ──────────────────
    raw_stream = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", REDPANDA_BROKERS)
        .option("subscribe",               TOPIC_NAME)
        .option("startingOffsets",         "latest")
        .option("failOnDataLoss",          "false")
        .load()
    )

    # ── Step 2: Parse JSON payload ─────────────────────────────
    events = (
        raw_stream
        .select(
            F.from_json(
                F.col("value").cast("string"),
                EVENT_SCHEMA
            ).alias("data")
        )
        .select("data.*")
        .withColumn("event_ts", F.to_timestamp("timestamp"))
        .withWatermark("event_ts", "5 minutes")   # allow 5min late arrivals
    )

    # ── Step 3A: Count errors per customer per 1-hour window ───
    error_agg = (
        events
        .filter(F.col("event_type") == "error")
        .groupBy(
            F.window("event_ts", "1 hour", "10 minutes"),  # sliding window
            "customer_id", "customer_name", "mrr", "plan"
        )
        .agg(
            F.count("*")                         .alias("error_count"),
            F.max("severity")                    .alias("max_severity"),
            F.collect_set("error_type")          .alias("error_types"),
        )
        .select(
            "customer_id", "customer_name", "mrr", "plan",
            "error_count", "max_severity", "error_types",
            F.lit("incident").alias("alert_type"),
            # Risk score = base score × log(error_count + 1), capped at 100
            F.least(
                F.lit(100),
                (F.col("error_count") * 12).cast("int")
            ).alias("risk_score"),
        )
        .filter(F.col("error_count") >= 5)        # only flag 5+ errors/hr
    )

    # ── Step 3B: Count support tickets per customer ────────────
    ticket_agg = (
        events
        .filter(F.col("event_type") == "support_ticket")
        .groupBy(
            F.window("event_ts", "24 hours", "1 hour"),
            "customer_id", "customer_name", "mrr", "plan"
        )
        .agg(
            F.count("*")             .alias("ticket_count"),
            F.max("open_hours")      .alias("max_open_hours"),
            F.max("severity")        .alias("max_severity"),
        )
        .select(
            "customer_id", "customer_name", "mrr", "plan",
            "ticket_count", "max_open_hours", "max_severity",
            F.lit("support").alias("alert_type"),
            F.least(
                F.lit(100),
                (F.col("ticket_count") * 20 +
                 F.when(F.col("max_open_hours") > 24, 20).otherwise(0)
                ).cast("int")
            ).alias("risk_score"),
        )
        .filter(F.col("ticket_count") >= 3)
    )

    # ── Step 3C: Silent churn — detect login drop ──────────────
    login_agg = (
        events
        .filter(F.col("event_type") == "login")
        .groupBy(
            F.window("event_ts", "7 days", "1 day"),
            "customer_id", "customer_name", "mrr", "plan"
        )
        .agg(
            F.count("*")                 .alias("login_count"),
            F.avg("features_used")       .alias("avg_features_used"),
        )
        .select(
            "customer_id", "customer_name", "mrr", "plan",
            "login_count", "avg_features_used",
            F.lit("silent_churn").alias("alert_type"),
            # Low login count = high risk
            F.greatest(
                F.lit(0),
                (F.lit(100) - F.col("login_count") * 5).cast("int")
            ).alias("risk_score"),
            F.lit("medium").alias("max_severity"),
        )
        .filter(F.col("login_count") <= 3)         # ≤3 logins in 7 days
    )

    # ── Step 4: Add final severity classification ──────────────
    def classify_severity(df):
        return df.withColumn(
            "severity",
            F.when(F.col("risk_score") >= CRITICAL_RISK_THRESHOLD, "critical")
            .when(F.col("risk_score") >= HIGH_RISK_THRESHOLD,       "high")
            .when(F.col("risk_score") >= 40,                        "medium")
            .otherwise("low")
        )

    error_alerts  = classify_severity(error_agg)
    ticket_alerts = classify_severity(ticket_agg)
    login_alerts  = classify_severity(login_agg)

    # ── Step 5: Write each stream to Postgres ─────────────────
    # Common JDBC write options
    jdbc_opts = {
        "url":    POSTGRES_JDBC_URL,
        "driver": "org.postgresql.Driver",
    }

    alert_columns = ["customer_id", "customer_name", "mrr", "plan",
                     "alert_type", "severity", "risk_score"]

    queries = []
    for stream, name in [
        (error_alerts,  "error_alerts"),
        (ticket_alerts, "ticket_alerts"),
        (login_alerts,  "login_alerts"),
    ]:
        q = (
            stream
            .select(alert_columns)
            .writeStream
            .foreachBatch(write_alerts_to_postgres)
            .outputMode("update")
            .option("checkpointLocation", f"{CHECKPOINT_DIR}/{name}")
            .trigger(processingTime="30 seconds")
            .start()
        )
        queries.append(q)
        print(f"✅ {name} stream started")

    print("All streams running. Waiting for termination...")
    spark.streams.awaitAnyTermination()


if __name__ == "__main__":
    main()
